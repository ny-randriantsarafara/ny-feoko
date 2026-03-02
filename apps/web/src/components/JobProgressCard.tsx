"use client";

import type { Tables } from "@/lib/supabase/types";
import { formatRelative } from "@/lib/format";

type Job = Tables<"jobs">;
type JobStatus = Job["status"];

interface JobProgressCardProps {
  readonly job: Job;
  readonly onViewRun?: (runId: string) => void;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function statusBadgeClass(status: JobStatus): string {
  switch (status) {
    case "queued":
      return "bg-gray-600 text-gray-200";
    case "running":
      return "bg-blue-600 text-white";
    case "done":
      return "bg-green-600 text-white";
    case "failed":
      return "bg-red-600 text-white";
    default:
      return "bg-gray-600 text-gray-200";
  }
}

function safeRunId(result: Record<string, unknown> | null): string | null {
  if (!result || typeof result.run_id !== "string") return null;
  return result.run_id;
}

function safeError(result: Record<string, unknown> | null): string | null {
  if (!result || typeof result.error !== "string") return null;
  return result.error;
}

export default function JobProgressCard({ job, onViewRun }: JobProgressCardProps) {
  const typeLabel = capitalize(job.type);
  const isComplete = job.status === "done";
  const runId = safeRunId(job.result);
  const errorMsg = safeError(job.result);

  return (
    <div
      className="p-4 rounded-lg border bg-[var(--bg-secondary)] border-[var(--border-color)]"
    >
      <div className="flex justify-between items-center">
        <span className="font-medium text-sm text-[var(--text-primary)]">
          {typeLabel}
        </span>
        <span
          className={`px-2 py-0.5 text-[11px] font-medium rounded ${statusBadgeClass(
            job.status,
          )}`}
        >
          {job.status}
        </span>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <div className="flex-1 h-1 bg-[var(--border-color)] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ${
              isComplete ? "bg-green-500" : "bg-blue-500"
            }`}
            style={{ width: `${job.progress}%` }}
          />
        </div>
        <span className="text-[11px] text-[var(--text-muted)] tabular-nums w-8 text-right">
          {Math.round(job.progress)}%
        </span>
      </div>

      {job.progress_message && (
        <p className="text-sm text-[var(--text-secondary)] mt-1.5 m-0">
          {job.progress_message}
        </p>
      )}

      {job.status === "done" && runId && onViewRun && (
        <button
          onClick={() => onViewRun(runId)}
          className="mt-2 px-3.5 py-1.5 bg-blue-700 text-white text-[13px] font-medium rounded-md border-none cursor-pointer hover:bg-blue-600 transition-colors"
        >
          View Run
        </button>
      )}

      {job.status === "failed" && errorMsg && (
        <p className="mt-2 text-sm text-red-500 m-0">{errorMsg}</p>
      )}

      <div className="mt-2 flex justify-end">
        <span className="text-[11px] text-[var(--text-muted)]">
          {formatRelative(new Date(job.created_at))}
        </span>
      </div>
    </div>
  );
}
