import { useCallback, useEffect, useRef, useState } from "react";
import type { Tables } from "@/lib/supabase/types";

type Job = Tables<"jobs">;

interface UseRecentJobsResult {
  readonly jobs: Job[];
  readonly loading: boolean;
  readonly error: string | null;
}

function isActive(status: Job["status"]): boolean {
  return status === "queued" || status === "running";
}

export function useRecentJobs(): UseRecentJobsResult {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await fetch("/api/jobs");
      if (!response.ok) {
        const data = await response.json();
        setError(data.error ?? "Failed to fetch jobs");
        return;
      }
      const data: Job[] = await response.json();
      setJobs(data);
      setError(null);

      const hasActive = data.some((j) => isActive(j.status));
      if (!hasActive && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch {
      setError("Failed to connect to API");
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchJobs().finally(() => setLoading(false));

    intervalRef.current = setInterval(fetchJobs, 5000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [fetchJobs]);

  return { jobs, loading, error };
}
