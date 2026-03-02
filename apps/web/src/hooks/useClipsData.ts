"use client";

import { useState, useEffect, useCallback } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Tables } from "@/lib/supabase/types";

export type Clip = Tables<"clips">;

export function useClipsData(
  runId: string | undefined,
  supabase: SupabaseClient,
  setError: (error: string | null) => void
) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetchClips = useCallback(async () => {
    if (!runId) return;

    const { data, error: fetchError } = await supabase
      .from("clips")
      .select("*")
      .eq("run_id", runId)
      .order("priority", { ascending: false })
      .order("created_at", { ascending: true });

    if (fetchError) {
      setError(fetchError.message);
      return;
    }

    const sorted = [...(data ?? [])].sort((a, b) => {
      const statusOrder: Record<string, number> = {
        pending: 0,
        corrected: 1,
        discarded: 2,
      };
      const aOrder = statusOrder[a.status];
      const bOrder = statusOrder[b.status];
      if (aOrder !== bOrder) return aOrder - bOrder;
      if (b.priority !== a.priority) return b.priority - a.priority;
      return a.created_at.localeCompare(b.created_at);
    });

    setClips(sorted);

    setSelectedId((prev) => {
      if (prev !== null) return prev;
      if (sorted.length === 0) return null;

      const lastClipKey = `lastClip-${runId}`;
      const stored = localStorage.getItem(lastClipKey);
      if (stored && sorted.some((c) => c.id === stored)) {
        return stored;
      }

      const firstPending = sorted.find((c) => c.status === "pending");
      return firstPending?.id ?? sorted[0].id;
    });
  }, [runId, supabase, setError]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  const selectedClip = clips.find((c) => c.id === selectedId);

  useEffect(() => {
    if (selectedId && runId) {
      localStorage.setItem(`lastClip-${runId}`, selectedId);
    }
  }, [selectedId, runId]);

  return {
    clips,
    setClips,
    selectedId,
    setSelectedId,
    selectedClip,
    fetchClips,
  };
}
