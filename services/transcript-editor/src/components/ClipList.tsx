"use client";

import { useEffect, useRef, useMemo } from "react";
import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

export type StatusFilter = "all" | "pending" | "corrected" | "discarded";

interface ClipListProps {
  clips: Clip[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: StatusFilter;
  onFilterChange: (filter: StatusFilter) => void;
  selectMode: boolean;
  selectedIds: ReadonlySet<string>;
  onToggleSelect: (id: string) => void;
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

export default function ClipList({
  clips,
  selectedId,
  onSelect,
  filter,
  onFilterChange,
  selectMode,
  selectedIds,
  onToggleSelect,
}: ClipListProps) {
  const doneCount = clips.filter((c) => c.status === "corrected" || c.status === "discarded").length;
  const total = clips.length;
  const progressPercent = (doneCount / Math.max(total, 1)) * 100;
  const selectedRef = useRef<HTMLDivElement>(null);

  const counts = useMemo(() => {
    const result: Record<StatusFilter, number> = { all: 0, pending: 0, corrected: 0, discarded: 0 };
    for (const clip of clips) {
      result.all++;
      result[clip.status]++;
    }
    return result;
  }, [clips]);

  const filteredClips = useMemo(() => {
    if (filter === "all") return clips;
    return clips.filter((c) => c.status === filter);
  }, [clips, filter]);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  return (
    <div className="flex-1 overflow-auto bg-[#111]">
      <div className="px-4 py-3 border-b border-gray-700 sticky top-0 bg-[#111] z-10">
        <div className="font-bold text-sm">
          Clips ({doneCount}/{total} done)
        </div>
        <div className="mt-1 h-1 bg-gray-700 rounded-sm">
          <div
            className="h-full bg-green-500 rounded-sm transition-[width] duration-300"
            style={{ width: `${progressPercent}%` }}
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

      {filteredClips.map((clip) => (
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
          {(clip.corrected_transcription ?? clip.draft_transcription) && (
            <div className={`text-gray-400 text-xs mt-0.5 truncate ${selectMode ? "ml-5" : ""}`}>
              {clip.corrected_transcription ?? clip.draft_transcription}
            </div>
          )}
        </div>
      ))}

      {filteredClips.length === 0 && (
        <div className="px-4 py-8 text-center text-gray-500 text-sm">
          No {filter === "all" ? "" : filter} clips
        </div>
      )}
    </div>
  );
}
