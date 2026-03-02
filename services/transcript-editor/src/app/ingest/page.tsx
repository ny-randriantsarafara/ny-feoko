"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import JobProgressCard from "@/components/JobProgressCard";
import { useJobPolling } from "@/hooks/useJobPolling";

function safeStringField(data: unknown, key: string): string | null {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const value = record[key];
  if (typeof value !== "string") return null;
  return value;
}

export default function IngestPage() {
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const { job, loading } = useJobPolling({ jobId, enabled: !!jobId });
  const jobActive = submitting || loading || (job !== null && job.status !== "done" && job.status !== "failed");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await fetch("/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, label }),
      });

      const data: unknown = await response.json();
      const id = safeStringField(data, "job_id");

      if (!response.ok) {
        setError(safeStringField(data, "error") ?? "Failed to start ingest");
        setSubmitting(false);
        return;
      }

      if (!id) {
        setError("Invalid response: missing job_id");
        setSubmitting(false);
        return;
      }

      setJobId(id);
    } catch {
      setError("Failed to connect to API");
    } finally {
      setSubmitting(false);
    }
  }

  function handleViewRun(runId: string) {
    router.push(`/runs/${runId}`);
  }

  return (
    <div className="max-w-[640px] mx-auto px-6 py-10">
      <Link
        href="/"
        className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        ← Back to runs
      </Link>

      <div className="mt-6">
        <h1 className="text-2xl font-semibold m-0">Ingest Audio</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Start a new pipeline run from a YouTube URL
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <div>
          <label
            htmlFor="url"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1.5"
          >
            YouTube URL
          </label>
          <input
            id="url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            required
            disabled={jobActive}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)]
              text-sm rounded-md px-3 py-2
              placeholder:text-[var(--text-muted)]
              focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500
              disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          />
        </div>

        <div>
          <label
            htmlFor="label"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1.5"
          >
            Label
          </label>
          <input
            id="label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. sunday-mass-01"
            disabled={jobActive}
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)]
              text-sm rounded-md px-3 py-2
              placeholder:text-[var(--text-muted)]
              focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500
              disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          />
        </div>

        {error && (
          <p className="text-sm text-red-500 m-0">{error}</p>
        )}

        <button
          type="submit"
          disabled={jobActive}
          className="px-4 py-2 bg-blue-700 text-white text-sm font-medium rounded-md border-none cursor-pointer
            hover:bg-blue-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed w-fit"
        >
          Start Ingest
        </button>
      </form>

      {job !== null && (
        <div className="mt-6">
          <JobProgressCard
            job={job}
            onViewRun={handleViewRun}
          />
        </div>
      )}
    </div>
  );
}
