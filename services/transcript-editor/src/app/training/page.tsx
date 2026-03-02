"use client";

import { useState } from "react";
import Link from "next/link";

interface ExportResult {
  readonly run_id: string;
  readonly dataset_dir: string;
}

function safeStringField(data: unknown, key: string): string | null {
  if (data === null || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  const value = record[key];
  if (typeof value !== "string") return null;
  return value;
}

function safeExportResult(data: unknown): ExportResult | null {
  const runId = safeStringField(data, "run_id");
  const datasetDir = safeStringField(data, "dataset_dir");
  if (!runId || !datasetDir) return null;
  return { run_id: runId, dataset_dir: datasetDir };
}

export default function TrainingPage() {
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);

    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });

      const data: unknown = await response.json();
      const exportResult = safeExportResult(data);

      if (!response.ok) {
        setError(safeStringField(data, "error") ?? "Export failed");
        setSubmitting(false);
        return;
      }

      if (!exportResult) {
        setError("Invalid response: missing run_id or dataset_dir");
        setSubmitting(false);
        return;
      }

      setResult(exportResult);
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
        ← Back to runs
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
            <label
              htmlFor="label"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1.5"
            >
              Run label
            </label>
            <input
              id="label"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. sunday-mass-01"
              required
              disabled={submitting}
              className="w-full bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)]
                text-sm rounded-md px-3 py-2
                placeholder:text-[var(--text-muted)]
                focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500
                disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            />
          </div>

          {error && <p className="text-sm text-red-500 m-0">{error}</p>}

          {result && (
            <div className="p-3 rounded-md bg-[var(--bg-tertiary)] border border-[var(--border-color)]">
              <p className="text-sm text-[var(--text-primary)] m-0">
                <span className="font-medium">run_id:</span> {result.run_id}
              </p>
              <p className="text-sm text-[var(--text-primary)] mt-1 m-0">
                <span className="font-medium">dataset_dir:</span>{" "}
                {result.dataset_dir}
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-blue-700 text-white text-sm font-medium rounded-md border-none cursor-pointer
              hover:bg-blue-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed w-fit"
          >
            Export Training Data
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
