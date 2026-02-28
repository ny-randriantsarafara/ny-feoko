"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { formatDuration } from "@/lib/format";
import RunCard from "@/components/RunCard";
import type { RunWithProgress } from "@/components/RunCard";

type TypeFilter = "all" | "extraction" | "reading";

const TYPE_TABS: { value: TypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "extraction", label: "Extraction" },
  { value: "reading", label: "Reading" },
];

export default function RunListPage() {
  const [runs, setRuns] = useState<RunWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    async function loadRuns() {
      const { data: runsData, error: runsError } = await supabase
        .from("runs")
        .select("*")
        .order("created_at", { ascending: false });

      if (runsError) {
        setError(runsError.message);
        setLoading(false);
        return;
      }

      const runIds = (runsData ?? []).map((r) => r.id);
      const { data: clipsData } = await supabase
        .from("clips")
        .select("run_id, status, duration_sec")
        .in("run_id", runIds);

      const statsMap = new Map<
        string,
        { total: number; done: number; duration: number }
      >();
      for (const clip of clipsData ?? []) {
        const stats = statsMap.get(clip.run_id) ?? {
          total: 0,
          done: 0,
          duration: 0,
        };
        stats.total += 1;
        if (clip.status === "corrected" || clip.status === "discarded") {
          stats.done += 1;
        }
        stats.duration += clip.duration_sec ?? 0;
        statsMap.set(clip.run_id, stats);
      }

      const runsWithProgress: RunWithProgress[] = (runsData ?? []).map(
        (run) => {
          const stats = statsMap.get(run.id) ?? {
            total: 0,
            done: 0,
            duration: 0,
          };
          return {
            ...run,
            total_clips: stats.total,
            done_clips: stats.done,
            total_duration_sec: stats.duration,
          };
        },
      );

      setRuns(runsWithProgress);
      setLoading(false);
    }

    loadRuns();
  }, [supabase]);

  const globalStats = useMemo(() => {
    const totalClips = runs.reduce((sum, r) => sum + r.total_clips, 0);
    const doneClips = runs.reduce((sum, r) => sum + r.done_clips, 0);
    const totalDuration = runs.reduce(
      (sum, r) => sum + r.total_duration_sec,
      0,
    );
    return { totalClips, doneClips, totalDuration };
  }, [runs]);

  const filteredRuns = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();

    const filtered = runs.filter((run) => {
      if (typeFilter !== "all" && run.type !== typeFilter) return false;
      if (query) {
        const matchesLabel = run.label.toLowerCase().includes(query);
        const matchesSource = run.source?.toLowerCase().includes(query) ?? false;
        if (!matchesLabel && !matchesSource) return false;
      }
      return true;
    });

    return filtered.sort((a, b) => {
      const aComplete =
        a.total_clips > 0 && a.done_clips === a.total_clips;
      const bComplete =
        b.total_clips > 0 && b.done_clips === b.total_clips;

      if (aComplete !== bComplete) return aComplete ? 1 : -1;

      if (!aComplete && !bComplete) {
        const aProgress =
          a.total_clips > 0 ? a.done_clips / a.total_clips : 0;
        const bProgress =
          b.total_clips > 0 ? b.done_clips / b.total_clips : 0;
        return aProgress - bProgress;
      }

      return (
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });
  }, [runs, typeFilter, searchQuery]);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[var(--text-secondary)]">Loading runs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[960px] mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-semibold m-0">
            Ambara Transcript Editor
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Select a run to start labelling
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => router.push("/read")}
            className="px-3.5 py-1.5 bg-blue-700 text-white text-[13px] font-medium rounded-md
              border-none cursor-pointer hover:bg-blue-600 transition-colors"
          >
            New Reading Session
          </button>
          <button
            onClick={handleLogout}
            className="px-3.5 py-1.5 bg-transparent text-[var(--text-secondary)] text-[13px]
              border border-[var(--border-color)] rounded-md cursor-pointer
              hover:border-gray-500 hover:text-[var(--text-primary)] transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {runs.length > 0 && (
        <div className="text-sm text-[var(--text-secondary)] pb-4 mb-4 border-b border-[var(--border-color)]">
          {globalStats.doneClips} / {globalStats.totalClips} clips corrected
          {" \u00B7 "}
          {formatDuration(globalStats.totalDuration)} audio
        </div>
      )}

      {/* Tabs + Search */}
      {runs.length > 0 && (
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex gap-1">
            {TYPE_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setTypeFilter(tab.value)}
                className={`px-3 py-1.5 text-[13px] rounded-md border-none cursor-pointer transition-colors ${
                  typeFilter === tab.value
                    ? "bg-[var(--bg-tertiary)] text-white"
                    : "bg-transparent text-[var(--text-secondary)] hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            placeholder="Search runs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border border-[var(--border-color)] text-[var(--text-primary)]
              text-sm rounded-md px-3 py-1.5 w-48
              placeholder:text-[var(--text-muted)]
              focus:outline-none focus:border-gray-500 transition-colors"
          />
        </div>
      )}

      {/* Empty state */}
      {runs.length === 0 && (
        <div className="text-center p-10 text-[var(--text-secondary)] border border-[var(--border-color)] rounded-lg bg-[var(--bg-secondary)]">
          <p className="m-0 mb-2">No runs found.</p>
          <p className="text-sm text-[var(--text-muted)] m-0">
            Sync your first extraction with:{" "}
            <code className="bg-[#222] px-1.5 py-0.5 rounded text-[var(--text-secondary)]">
              ./ambara sync --dir data/output/your-run
            </code>
          </p>
        </div>
      )}

      {/* No results for current filter */}
      {runs.length > 0 && filteredRuns.length === 0 && (
        <div className="text-center py-10 text-[var(--text-muted)]">
          No runs match your filters.
        </div>
      )}

      {/* Run list */}
      <div className="flex flex-col gap-3">
        {filteredRuns.map((run) => (
          <RunCard
            key={run.id}
            run={run}
            onClick={() => router.push(`/runs/${run.id}`)}
          />
        ))}
      </div>
    </div>
  );
}
