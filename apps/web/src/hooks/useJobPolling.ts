import { useCallback, useEffect, useRef, useState } from "react";
import type { Tables } from "@/lib/supabase/types";

type Job = Tables<"jobs">;

interface UseJobPollingOptions {
  readonly jobId: string | null;
  readonly intervalMs?: number;
  readonly enabled?: boolean;
}

interface UseJobPollingResult {
  readonly job: Job | null;
  readonly loading: boolean;
  readonly error: string | null;
}

export function useJobPolling({
  jobId,
  intervalMs = 3000,
  enabled = true,
}: UseJobPollingOptions): UseJobPollingResult {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) {
        const data = await response.json();
        setError(data.error ?? "Failed to fetch job status");
        return;
      }
      const data: Job = await response.json();
      setJob(data);
      setError(null);
      if (data.status === "done" || data.status === "failed") {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch {
      setError("Failed to connect to API");
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !enabled) return;
    setLoading(true);
    fetchJob().finally(() => setLoading(false));
    intervalRef.current = setInterval(fetchJob, intervalMs);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, intervalMs, enabled, fetchJob]);

  return { job, loading, error };
}
