"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Tables } from "@/lib/supabase/types";
import ClipList from "@/components/ClipList";
import ClipEditor from "@/components/ClipEditor";

type Clip = Tables<"clips">;

export default function RunEditorPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const supabase = createClient();

  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [audioUrls, setAudioUrls] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUserId(data.user?.id ?? null);
    });
  }, [supabase]);

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
      const statusOrder = { pending: 0, corrected: 1, discarded: 2 };
      const aOrder = statusOrder[a.status];
      const bOrder = statusOrder[b.status];
      if (aOrder !== bOrder) return aOrder - bOrder;
      if (b.priority !== a.priority) return b.priority - a.priority;
      return a.created_at.localeCompare(b.created_at);
    });

    setClips(sorted);

    if (sorted.length > 0 && selectedId === null) {
      const firstPending = sorted.find((c) => c.status === "pending");
      setSelectedId(firstPending?.id ?? sorted[0].id);
    }
  }, [runId, supabase, selectedId]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  const getAudioUrl = useCallback(async (clip: Clip): Promise<string> => {
    const cached = audioUrls[clip.id];
    if (cached) return cached;

    const storagePath = `${runId}/${clip.file_name}`;
    const { data } = await supabase.storage
      .from("clips")
      .createSignedUrl(storagePath, 3600);

    const url = data?.signedUrl ?? "";
    setAudioUrls((prev) => ({ ...prev, [clip.id]: url }));
    return url;
  }, [runId, supabase, audioUrls]);

  const [currentAudioUrl, setCurrentAudioUrl] = useState("");

  useEffect(() => {
    const selected = clips.find((c) => c.id === selectedId);
    if (!selected) return;

    getAudioUrl(selected).then(setCurrentAudioUrl);
  }, [selectedId, clips, getAudioUrl]);

  const handleSave = useCallback(
    async (transcription: string, status: "corrected" | "discarded") => {
      if (!selectedId || !userId) return;

      const currentClip = clips.find((c) => c.id === selectedId);
      const previousValue = currentClip?.corrected_transcription ?? currentClip?.draft_transcription ?? "";

      const { error: updateError } = await supabase
        .from("clips")
        .update({
          corrected_transcription: transcription,
          status,
          corrected_at: new Date().toISOString(),
          corrected_by: userId,
        })
        .eq("id", selectedId);

      if (updateError) {
        setError(updateError.message);
        return;
      }

      await supabase.from("clip_edits").insert({
        clip_id: selectedId,
        editor_id: userId,
        field: "corrected_transcription",
        old_value: previousValue,
        new_value: transcription,
      });

      setClips((prev) =>
        prev.map((c) =>
          c.id === selectedId
            ? {
                ...c,
                corrected_transcription: transcription,
                status,
                corrected_at: new Date().toISOString(),
                corrected_by: userId,
              }
            : c
        )
      );
    },
    [selectedId, userId, clips, supabase]
  );

  const selectedIndex = clips.findIndex((c) => c.id === selectedId);

  const goNext = useCallback(() => {
    if (selectedIndex < 0 || selectedIndex >= clips.length - 1) return;
    setSelectedId(clips[selectedIndex + 1].id);
  }, [selectedIndex, clips]);

  const goPrev = useCallback(() => {
    if (selectedIndex <= 0) return;
    setSelectedId(clips[selectedIndex - 1].id);
  }, [selectedIndex, clips]);

  const selectedClip = clips.find((c) => c.id === selectedId);

  if (error) {
    return (
      <div style={{ padding: 40, color: "#ef4444" }}>
        <h2>Error</h2>
        <pre>{error}</pre>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <div style={{ display: "flex", flexDirection: "column", width: 300, borderRight: "1px solid #333" }}>
        <div style={{ padding: "8px 16px", borderBottom: "1px solid #333", display: "flex", alignItems: "center" }}>
          <button
            onClick={() => router.push("/")}
            style={{
              background: "none",
              border: "none",
              color: "#3b82f6",
              cursor: "pointer",
              fontSize: 13,
              padding: "4px 0",
            }}
          >
            ← All runs
          </button>
        </div>
        <ClipList clips={clips} selectedId={selectedId} onSelect={setSelectedId} />
      </div>
      {selectedClip ? (
        <ClipEditor
          clip={selectedClip}
          audioUrl={currentAudioUrl}
          onSave={handleSave}
          onNext={goNext}
          onPrev={goPrev}
        />
      ) : (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#666" }}>
          {clips.length === 0 ? "Loading clips..." : "Select a clip to start editing"}
        </div>
      )}
    </div>
  );
}
