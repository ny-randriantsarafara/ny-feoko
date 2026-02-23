"use client";

import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

interface ClipListProps {
  clips: Clip[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const STATUS_BORDER_CLASSES: Record<string, string> = {
  pending: "border-l-gray-500",
  corrected: "border-l-green-500",
  discarded: "border-l-red-500",
};

export default function ClipList({ clips, selectedId, onSelect }: ClipListProps) {
  const correctedCount = clips.filter((c) => c.status === "corrected").length;
  const total = clips.length;
  const progressPercent = (correctedCount / Math.max(total, 1)) * 100;

  return (
    <div className="flex-1 overflow-auto bg-[#111]">
      {/* Header with progress */}
      <div className="px-4 py-3 border-b border-gray-700 sticky top-0 bg-[#111] z-10">
        <div className="font-bold text-sm">
          Clips ({correctedCount}/{total} corrected)
        </div>
        <div className="mt-1 h-1 bg-gray-700 rounded-sm">
          <div
            className="h-full bg-green-500 rounded-sm transition-[width] duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Clip items */}
      {clips.map((clip) => (
        <div
          key={clip.id}
          onClick={() => onSelect(clip.id)}
          className={`px-4 py-2 cursor-pointer border-l-[3px] text-[13px] hover:bg-gray-800/50 ${
            STATUS_BORDER_CLASSES[clip.status] ?? "border-l-gray-500"
          } ${clip.id === selectedId ? "bg-slate-800" : ""}`}
        >
          <div className="flex justify-between items-center">
            <span className="font-mono truncate">
              {clip.file_name.replace("clips/", "")}
            </span>
            <span className="text-gray-500 ml-2 shrink-0">
              {(clip.duration_sec ?? 0).toFixed(1)}s
            </span>
          </div>
          {(clip.corrected_transcription ?? clip.draft_transcription) && (
            <div className="text-gray-400 text-xs mt-0.5 truncate">
              {clip.corrected_transcription ?? clip.draft_transcription}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
