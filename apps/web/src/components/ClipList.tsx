"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

export type StatusFilter = "all" | "pending" | "corrected" | "discarded";

interface ClipListProps {
  readonly clips: Clip[];
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
  readonly filter: StatusFilter;
  readonly onFilterChange: (filter: StatusFilter) => void;
  readonly selectMode: boolean;
  readonly selectedIds: ReadonlySet<string>;
  readonly onToggleSelect: (id: string) => void;
  readonly onMergeBack?: (clipId: string) => void;
}

const STATUS_BORDER_CLASSES: Record<string, string> = {
  pending: "border-l-gray-500",
  corrected: "border-l-green-500",
  discarded: "border-l-red-500",
};

const FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "corrected", label: "Corrected" },
  { value: "discarded", label: "Discarded" },
];

function isSplitOrigin(clip: Clip): boolean {
  if (clip.status !== "discarded" || !clip.corrected_transcription) return false;
  try {
    const parsed = JSON.parse(clip.corrected_transcription);
    return parsed._splitOrigin === true;
  } catch {
    return false;
  }
}

export default function ClipList({
  clips,
  selectedId,
  onSelect,
  filter,
  onFilterChange,
  selectMode,
  selectedIds,
  onToggleSelect,
  onMergeBack,
}: ClipListProps) {
  const total = clips.length;
  const correctedCount = clips.filter((c) => c.status === "corrected").length;
  const discardedCount = clips.filter((c) => c.status === "discarded").length;
  const doneCount = correctedCount + discardedCount;
  const correctedPercent = (correctedCount / Math.max(total, 1)) * 100;
  const discardedPercent = (discardedCount / Math.max(total, 1)) * 100;
  const selectedRef = useRef<HTMLDivElement>(null);

  const counts = useMemo(() => {
    const result: Record<StatusFilter, number> = { all: 0, pending: 0, corrected: 0, discarded: 0 };
    for (const clip of clips) {
      result.all++;
      result[clip.status]++;
    }
    return result;
  }, [clips]);

  const PAGE_SIZE = 50;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const filteredClips = useMemo(() => {
    if (filter === "all") return clips;
    return clips.filter((c) => c.status === filter);
  }, [clips, filter]);

  const visibleClips = useMemo(() => {
    const selectedIdx = filteredClips.findIndex((c) => c.id === selectedId);
    const neededCount = selectedIdx >= 0 ? Math.max(visibleCount, selectedIdx + 1) : visibleCount;
    return filteredClips.slice(0, neededCount);
  }, [filteredClips, visibleCount, selectedId]);

  const hasMore = visibleClips.length < filteredClips.length;

  const showMore = useCallback(() => {
    setVisibleCount((prev) => prev + PAGE_SIZE);
  }, []);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [filter]);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  return (
    <div className="flex-1 overflow-auto bg-[#111]">
      <div className="px-4 py-3 border-b border-gray-700 sticky top-0 bg-[#111] z-10">
        <div className="font-bold text-sm">
          Clips ({doneCount}/{total} done)
        </div>
        <div className="mt-1 h-1 bg-gray-700 rounded-sm flex overflow-hidden">
          <div
            className="h-full bg-green-500 transition-[width] duration-300"
            style={{ width: `${correctedPercent}%` }}
          />
          <div
            className="h-full bg-red-500 transition-[width] duration-300"
            style={{ width: `${discardedPercent}%` }}
          />
        </div>
        <div className="mt-2 flex gap-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onFilterChange(opt.value)}
              className={`px-2 py-0.5 rounded text-xs transition-colors ${
                filter === opt.value
                  ? "bg-blue-700 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {opt.label} ({counts[opt.value]})
            </button>
          ))}
        </div>
      </div>

      {visibleClips.map((clip) => (
        <div
          key={clip.id}
          ref={clip.id === selectedId ? selectedRef : undefined}
          onClick={() => {
            if (selectMode) {
              onToggleSelect(clip.id);
            } else {
              onSelect(clip.id);
            }
          }}
          className={`px-4 py-2 cursor-pointer border-l-[3px] text-[13px] hover:bg-gray-800/50 ${
            STATUS_BORDER_CLASSES[clip.status] ?? "border-l-gray-500"
          } ${clip.id === selectedId && !selectMode ? "bg-slate-800" : ""}`}
        >
          <div className="flex justify-between items-center gap-2">
            {selectMode && (
              <input
                type="checkbox"
                checked={selectedIds.has(clip.id)}
                onChange={() => onToggleSelect(clip.id)}
                onClick={(e) => e.stopPropagation()}
                className="shrink-0 accent-red-500"
              />
            )}
            <span className="font-mono truncate flex-1">
              {clip.file_name.replace("clips/", "")}
            </span>
            <span className="text-gray-500 shrink-0">
              {(clip.duration_sec ?? 0).toFixed(1)}s
            </span>
          </div>
          {isSplitOrigin(clip) ? (
            <div className={`flex items-center gap-2 mt-0.5 ${selectMode ? "ml-5" : ""}`}>
              <span className="text-xs text-purple-400">Split origin</span>
              {onMergeBack && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onMergeBack(clip.id);
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300 hover:underline"
                >
                  Merge Back
                </button>
              )}
            </div>
          ) : (clip.corrected_transcription ?? clip.draft_transcription) ? (
            <div className={`text-gray-400 text-xs mt-0.5 truncate ${selectMode ? "ml-5" : ""}`}>
              {clip.corrected_transcription ?? clip.draft_transcription}
            </div>
          ) : null}
        </div>
      ))}

      {hasMore && (
        <button
          onClick={showMore}
          className="w-full py-2 text-sm text-blue-400 hover:text-blue-300 hover:bg-gray-800/50 transition-colors"
        >
          Show more ({filteredClips.length - visibleClips.length} remaining)
        </button>
      )}

      {filteredClips.length === 0 && (
        <div className="px-4 py-8 text-center text-gray-500 text-sm">
          No {filter === "all" ? "" : filter} clips
        </div>
      )}
    </div>
  );
}
