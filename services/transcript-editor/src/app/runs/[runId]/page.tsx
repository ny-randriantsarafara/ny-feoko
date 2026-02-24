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
  const [sidebarOpen, setSidebarOpen] = useState(false);

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

    setSelectedId((prev) => {
      if (prev !== null) return prev;
      if (sorted.length === 0) return null;
      const firstPending = sorted.find((c) => c.status === "pending");
      return firstPending?.id ?? sorted[0].id;
    });
  }, [runId, supabase]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  const getAudioUrl = useCallback(async (clip: Clip): Promise<string> => {
    const storagePath = `${runId}/${clip.file_name}`;
    const { data } = await supabase.storage
      .from("clips")
      .createSignedUrl(storagePath, 3600);

    const url = data?.signedUrl ?? "";
    setAudioUrls((prev) => ({ ...prev, [clip.id]: url }));
    return url;
  }, [runId, supabase]);

  const [currentAudioUrl, setCurrentAudioUrl] = useState("");

  useEffect(() => {
    const selected = clips.find((c) => c.id === selectedId);
    if (!selected) return;

    const cached = audioUrls[selected.id];
    if (cached) {
      setCurrentAudioUrl(cached);
    } else {
      getAudioUrl(selected).then(setCurrentAudioUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const handleAutoSave = useCallback(
    async (transcription: string) => {
      if (!selectedId || !userId) return;

      await supabase
        .from("clips")
        .update({ corrected_transcription: transcription })
        .eq("id", selectedId);

      setClips((prev) =>
        prev.map((c) =>
          c.id === selectedId
            ? { ...c, corrected_transcription: transcription }
            : c
        )
      );
    },
    [selectedId, userId, supabase]
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
  const isLastClip = selectedIndex === clips.length - 1;

  const handleClipSelect = useCallback((id: string) => {
    setSelectedId(id);
    setSidebarOpen(false);
  }, []);

  if (error) {
    return (
      <div className="p-10 text-red-500">
        <h2>Error</h2>
        <pre>{error}</pre>
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row h-screen overflow-hidden">
      {/* Mobile header with toggle */}
      <div className="md:hidden flex items-center justify-between px-4 py-2 border-b border-gray-700 bg-[#111]">
        <button
          onClick={() => router.push("/")}
          className="text-blue-500 text-sm"
        >
          ← All runs
        </button>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="text-gray-400 text-sm px-2 py-1 border border-gray-600 rounded"
        >
          {sidebarOpen ? "Hide clips" : `Clips (${clips.length})`}
        </button>
      </div>

      {/* Sidebar - always visible on md+, toggleable on mobile */}
      <div
        className={`${
          sidebarOpen ? "flex" : "hidden"
        } md:flex flex-col w-full md:w-[300px] border-r border-gray-700 bg-[#111] max-h-[40vh] md:max-h-none overflow-hidden`}
      >
        {/* Desktop back link */}
        <div className="hidden md:flex px-4 py-2 border-b border-gray-700 items-center">
          <button
            onClick={() => router.push("/")}
            className="text-blue-500 text-sm hover:underline"
          >
            ← All runs
          </button>
        </div>
        <ClipList clips={clips} selectedId={selectedId} onSelect={handleClipSelect} />
      </div>

      {/* Main editor area */}
      {selectedClip ? (
        <ClipEditor
          clip={selectedClip}
          audioUrl={currentAudioUrl}
          onSave={handleSave}
          onAutoSave={handleAutoSave}
          onNext={goNext}
          onPrev={goPrev}
          isLastClip={isLastClip}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          {clips.length === 0 ? "Loading clips..." : "Select a clip to start editing"}
        </div>
      )}
    </div>
  );
}
