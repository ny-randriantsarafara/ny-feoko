"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { formatDuration } from "@/lib/format";
import type { Tables } from "@/lib/supabase/types";

type Run = Tables<"runs">;

interface RunWithProgress extends Run {
  total_clips: number;
  done_clips: number;
  total_duration_sec: number;
}

export default function RunListPage() {
  const [runs, setRuns] = useState<RunWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

      // Fetch all clips in one query instead of N+1
      const runIds = (runsData ?? []).map((r) => r.id);
      const { data: clipsData } = await supabase
        .from("clips")
        .select("run_id, status, duration_sec")
        .in("run_id", runIds);

      // Aggregate per run
      const statsMap = new Map<string, { total: number; done: number; duration: number }>();
      for (const clip of clipsData ?? []) {
        const stats = statsMap.get(clip.run_id) ?? { total: 0, done: 0, duration: 0 };
        stats.total += 1;
        if (clip.status === "corrected" || clip.status === "discarded") {
          stats.done += 1;
        }
        stats.duration += clip.duration_sec ?? 0;
        statsMap.set(clip.run_id, stats);
      }

      const runsWithProgress: RunWithProgress[] = (runsData ?? []).map((run) => {
        const stats = statsMap.get(run.id) ?? { total: 0, done: 0, duration: 0 };
        return {
          ...run,
          total_clips: stats.total,
          done_clips: stats.done,
          total_duration_sec: stats.duration,
        };
      });

      setRuns(runsWithProgress);
      setLoading(false);
    }

    loadRuns();
  }, [supabase]);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  if (loading) {
    return (
      <div style={centerStyle}>
        <p style={{ color: "#888" }}>Loading runs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={centerStyle}>
        <p style={{ color: "#ef4444" }}>{error}</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "40px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28 }}>Ambara Transcript Editor</h1>
          <p style={{ color: "#888", margin: "4px 0 0" }}>Select a run to start labelling</p>
        </div>
        <button onClick={handleLogout} style={logoutButtonStyle}>
          Sign out
        </button>
      </div>

      {runs.length === 0 && (
        <div style={{ textAlign: "center", padding: 40, color: "#888" }}>
          <p>No runs found.</p>
          <p style={{ fontSize: 14 }}>
            Sync your first extraction with:&nbsp;
            <code style={{ background: "#222", padding: "2px 6px", borderRadius: 4 }}>
              ./ambara sync --dir data/output/your-run
            </code>
          </p>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {runs.map((run) => {
          const progress = run.total_clips > 0
            ? (run.done_clips / run.total_clips) * 100
            : 0;

          return (
            <div
              key={run.id}
              onClick={() => router.push(`/runs/${run.id}`)}
              style={runCardStyle}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 16 }}>{run.label}</div>
                  {run.source && (
                    <div style={{ color: "#666", fontSize: 13, marginTop: 2 }}>{run.source}</div>
                  )}
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 14, color: "#888" }}>
                    {run.done_clips}/{run.total_clips} clips · {formatDuration(run.total_duration_sec)}
                  </div>
                  <div style={{ fontSize: 12, color: "#666" }}>
                    {new Date(run.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 8, height: 4, background: "#333", borderRadius: 2 }}>
                <div
                  style={{
                    height: "100%",
                    width: `${progress}%`,
                    background: progress === 100 ? "#22c55e" : "#3b82f6",
                    borderRadius: 2,
                    transition: "width 0.3s",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const centerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "100vh",
};

const runCardStyle: React.CSSProperties = {
  padding: 16,
  background: "#111",
  border: "1px solid #333",
  borderRadius: 8,
  cursor: "pointer",
};

const logoutButtonStyle: React.CSSProperties = {
  padding: "6px 14px",
  background: "transparent",
  color: "#888",
  border: "1px solid #333",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13,
};
