"use client";

import type { Tables } from "@/lib/supabase/types";
import { formatDuration } from "@/lib/format";

type Run = Tables<"runs">;

export interface RunWithProgress extends Run {
  total_clips: number;
  done_clips: number;
  total_duration_sec: number;
}

interface RunCardProps {
  readonly run: RunWithProgress;
  readonly onClick: () => void;
}

export default function RunCard({ run, onClick }: RunCardProps) {
  const progress =
    run.total_clips > 0 ? (run.done_clips / run.total_clips) * 100 : 0;
  const isComplete = progress === 100 && run.total_clips > 0;
  const progressPercent = Math.round(progress);

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border cursor-pointer transition-colors
        bg-[var(--bg-secondary)] border-[var(--border-color)]
        hover:border-gray-600 hover:bg-[#161616]
        ${isComplete ? "opacity-70" : ""}`}
    >
      <div className="flex justify-between items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-base">{run.label}</span>
            {run.type === "reading" && (
              <span className="px-1.5 py-px text-[11px] font-medium rounded bg-blue-950 text-blue-400">
                reading
              </span>
            )}
          </div>
          {run.source && (
            <div className="text-[var(--text-muted)] text-[13px] mt-0.5">
              {run.source}
            </div>
          )}
        </div>
        <div className="text-right shrink-0 ml-4">
          <div className="text-sm text-[var(--text-secondary)]">
            {run.done_clips}/{run.total_clips} clips &middot;{" "}
            {formatDuration(run.total_duration_sec)}
          </div>
          <div className="text-xs text-[var(--text-muted)]">
            {new Date(run.created_at).toLocaleDateString()}
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <div className="flex-1 h-1 bg-[var(--border-color)] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ${
              isComplete ? "bg-green-500" : "bg-blue-500"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[11px] text-[var(--text-muted)] tabular-nums w-8 text-right">
          {progressPercent}%
        </span>
      </div>
    </div>
  );
}
