"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface RunOption {
  readonly id: string;
  readonly label: string;
  readonly type: string;
  readonly created_at: string;
}

interface ExportResult {
  readonly dataset_dir: string;
}

function safeStringField(data: unknown, key: string): string | null {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const value = record[key];
  if (typeof value !== "string") return null;
  return value;
}

export default function TrainingPage() {
  const [runs, setRuns] = useState<readonly RunOption[]>([]);
  const [selectedRunIds, setSelectedRunIds] = useState<readonly string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);

  useEffect(() => {
    fetch("/api/runs")
      .then((res) => res.json())
      .then((data: unknown) => {
        if (Array.isArray(data)) {
          setRuns(data as readonly RunOption[]);
        }
      })
      .catch(() => setError("Failed to load runs"))
      .finally(() => setLoadingRuns(false));
  }, []);

  function toggleRun(runId: string) {
    setSelectedRunIds((prev) =>
      prev.includes(runId)
        ? prev.filter((id) => id !== runId)
        : [...prev, runId],
    );
  }

  async function handleExport(e: React.FormEvent) {
    e.preventDefault();
    if (selectedRunIds.length === 0) return;
    setError(null);
    setResult(null);
    setSubmitting(true);

    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_ids: selectedRunIds }),
      });

      const data: unknown = await response.json();

      if (!response.ok) {
        setError(safeStringField(data, "error") ?? "Export failed");
        setSubmitting(false);
        return;
      }

      const datasetDir = safeStringField(data, "dataset_dir");
      if (!datasetDir) {
        setError("Invalid response: missing dataset_dir");
        setSubmitting(false);
        return;
      }

      setResult({ dataset_dir: datasetDir });
    } catch {
      setError("Failed to connect to API");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-[640px] mx-auto px-6 py-10">
      <Link
        href="/"
        className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        &larr; Back to runs
      </Link>

      <div className="mt-6">
        <h1 className="text-2xl font-semibold m-0">Training</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Export training data and fine-tune with Colab
        </p>
      </div>

      <section className="mt-8">
        <h2 className="text-base font-medium text-[var(--text-primary)] mb-3">
          Export Training Data
        </h2>
        <form onSubmit={handleExport} className="flex flex-col gap-3">
          <div>
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
              Select runs
            </label>
            {loadingRuns ? (
              <p className="text-sm text-[var(--text-muted)]">Loading runs...</p>
            ) : runs.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">No runs found</p>
            ) : (
              <div className="flex flex-col gap-1 max-h-48 overflow-y-auto border border-[var(--border-color)] rounded-md p-2 bg-[var(--bg-secondary)]">
                {runs.map((run) => (
                  <label
                    key={run.id}
                    className="flex items-center gap-2 text-sm text-[var(--text-primary)] cursor-pointer px-1 py-0.5 rounded hover:bg-[var(--bg-tertiary)]"
                  >
                    <input
                      type="checkbox"
                      checked={selectedRunIds.includes(run.id)}
                      onChange={() => toggleRun(run.id)}
                      disabled={submitting}
                      className="accent-blue-600"
                    />
                    <span>{run.label}</span>
                    <span className="text-[var(--text-muted)] text-xs ml-auto">
                      {run.type}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {error && <p className="text-sm text-red-500 m-0">{error}</p>}

          {result && (
            <div className="p-3 rounded-md bg-[var(--bg-tertiary)] border border-[var(--border-color)]">
              <p className="text-sm text-[var(--text-primary)] m-0">
                <span className="font-medium">dataset_dir:</span>{" "}
                {result.dataset_dir}
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || selectedRunIds.length === 0}
            className="px-4 py-2 bg-blue-700 text-white text-sm font-medium rounded-md border-none cursor-pointer
              hover:bg-blue-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed w-fit"
          >
            {selectedRunIds.length === 0
              ? "Select runs to export"
              : `Export ${selectedRunIds.length} run${selectedRunIds.length > 1 ? "s" : ""}`}
          </button>
        </form>
      </section>

      <section className="mt-10">
        <h2 className="text-base font-medium text-[var(--text-primary)] mb-3">
          Fine-tune with Colab
        </h2>
        <ol className="text-sm text-[var(--text-secondary)] list-decimal list-inside space-y-2 m-0 pl-0">
          <li>Export training data using the button above</li>
          <li>
            Open the{" "}
            <a
              href="#"
              className="text-blue-400 hover:underline"
            >
              Colab notebook
            </a>
          </li>
          <li>Upload the exported dataset or point to Supabase</li>
          <li>Run all cells to start training</li>
        </ol>
      </section>
    </div>
  );
}
