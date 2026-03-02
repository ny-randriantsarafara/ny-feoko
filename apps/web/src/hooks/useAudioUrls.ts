"use client";

import { useState, useEffect, useCallback } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Clip } from "./useClipsData";

const URL_MAX_AGE_MS = 50 * 60 * 1000;

export function useAudioUrls(
  runId: string | undefined,
  clips: Clip[],
  filteredClips: Clip[],
  selectedId: string | null,
  supabase: SupabaseClient
) {
  const [audioUrls, setAudioUrls] = useState<
    Record<string, { url: string; fetchedAt: number }>
  >({});
  const [currentAudioUrl, setCurrentAudioUrl] = useState("");

  const getAudioUrl = useCallback(
    async (clip: Clip, forceRefresh = false): Promise<string> => {
      if (!forceRefresh) {
        const cached = audioUrls[clip.id];
        if (cached && Date.now() - cached.fetchedAt < URL_MAX_AGE_MS) {
          return cached.url;
        }
      }

      const storagePath = `${runId}/${clip.file_name}`;
      const { data } = await supabase.storage
        .from("clips")
        .createSignedUrl(storagePath, 3600);

      const url = data?.signedUrl ?? "";
      setAudioUrls((prev) => ({ ...prev, [clip.id]: { url, fetchedAt: Date.now() } }));
      return url;
    },
    [runId, supabase, audioUrls]
  );

  const refreshAudioUrl = useCallback(async () => {
    const selected = clips.find((c) => c.id === selectedId);
    if (!selected) return;
    const url = await getAudioUrl(selected, true);
    setCurrentAudioUrl(url);
  }, [clips, selectedId, getAudioUrl]);

  useEffect(() => {
    const selected = clips.find((c) => c.id === selectedId);
    if (!selected) return;

    const cached = audioUrls[selected.id];
    if (cached && Date.now() - cached.fetchedAt < URL_MAX_AGE_MS) {
      setCurrentAudioUrl(cached.url);
    } else {
      getAudioUrl(selected).then(setCurrentAudioUrl).catch(() => setCurrentAudioUrl(""));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, clips]);

  useEffect(() => {
    const selectedIdx = filteredClips.findIndex((c) => c.id === selectedId);
    if (selectedIdx < 0) return;

    const upcoming = filteredClips.slice(selectedIdx + 1, selectedIdx + 3);

    for (const clip of upcoming) {
      getAudioUrl(clip)
        .then((url) => {
          if (url) {
            const audio = new Audio(url);
            audio.preload = "auto";
            audio.load();
          }
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, filteredClips]);

  useEffect(() => {
    const interval = setInterval(() => {
      const selected = clips.find((c) => c.id === selectedId);
      if (!selected) return;

      const cached = audioUrls[selected.id];
      if (cached && Date.now() - cached.fetchedAt > 45 * 60 * 1000) {
        getAudioUrl(selected, true).then(setCurrentAudioUrl).catch(() => setCurrentAudioUrl(""));
      }
    }, 10 * 60 * 1000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, clips]);

  return { currentAudioUrl, refreshAudioUrl };
}
