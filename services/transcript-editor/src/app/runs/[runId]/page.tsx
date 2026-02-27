"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Tables } from "@/lib/supabase/types";
import ClipList from "@/components/ClipList";
import type { StatusFilter } from "@/components/ClipList";
import ClipEditor from "@/components/ClipEditor";
import SessionStats from "@/components/SessionStats";

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
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [selectMode, setSelectMode] = useState(false);
  const [bulkSelectedIds, setBulkSelectedIds] = useState<Set<string>>(new Set());
  const [sessionDoneCount, setSessionDoneCount] = useState(0);
  const sessionStartRef = useRef(Date.now());

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

  const filteredClips = useMemo(() => {
    if (filter === "all") return clips;
    return clips.filter((c) => c.status === filter);
  }, [clips, filter]);

  const pendingCount = useMemo(
    () => clips.filter((c) => c.status === "pending").length,
    [clips],
  );

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

      setSessionDoneCount((prev) => prev + 1);
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

  const selectedIndex = filteredClips.findIndex((c) => c.id === selectedId);

  const goNext = useCallback(() => {
    if (selectedIndex < 0 || selectedIndex >= filteredClips.length - 1) return;
    setSelectedId(filteredClips[selectedIndex + 1].id);
  }, [selectedIndex, filteredClips]);

  const goPrev = useCallback(() => {
    if (selectedIndex <= 0) return;
    setSelectedId(filteredClips[selectedIndex - 1].id);
  }, [selectedIndex, filteredClips]);

  const selectedClip = clips.find((c) => c.id === selectedId);
  const isLastClip = selectedIndex === filteredClips.length - 1;

  const handleClipSelect = useCallback((id: string) => {
    setSelectedId(id);
    setSidebarOpen(false);
  }, []);

  const handleToggleBulkSelect = useCallback((id: string) => {
    setBulkSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleBulkDiscard = useCallback(async () => {
    if (bulkSelectedIds.size === 0 || !userId) return;

    const ids = [...bulkSelectedIds];

    const { error: updateError } = await supabase
      .from("clips")
      .update({
        status: "discarded" as const,
        corrected_at: new Date().toISOString(),
        corrected_by: userId,
      })
      .in("id", ids);

    if (updateError) {
      setError(updateError.message);
      return;
    }

    setClips((prev) =>
      prev.map((c) =>
        bulkSelectedIds.has(c.id)
          ? { ...c, status: "discarded" as const, corrected_at: new Date().toISOString(), corrected_by: userId }
          : c
      )
    );

    setSessionDoneCount((prev) => prev + ids.length);
    setBulkSelectedIds(new Set());
    setSelectMode(false);
  }, [bulkSelectedIds, userId, supabase]);

  const toggleSelectMode = useCallback(() => {
    setSelectMode((prev) => {
      if (prev) {
        setBulkSelectedIds(new Set());
      }
      return !prev;
    });
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
      <div className="md:hidden flex items-center justify-between px-4 py-2 border-b border-gray-700 bg-[#111]">
        <button
          onClick={() => router.push("/")}
          className="text-blue-500 text-sm"
        >
          ← All runs
        </button>
        <div className="flex gap-2">
          {sidebarOpen && (
            <button
              onClick={toggleSelectMode}
              className={`text-xs px-2 py-0.5 rounded border ${
                selectMode
                  ? "border-red-500 text-red-400"
                  : "border-gray-600 text-gray-400"
              }`}
            >
              {selectMode ? "Cancel" : "Select"}
            </button>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-400 text-sm px-2 py-1 border border-gray-600 rounded"
          >
            {sidebarOpen ? "Hide clips" : `Clips (${clips.length})`}
          </button>
        </div>
      </div>

      <div
        className={`${
          sidebarOpen ? "flex" : "hidden"
        } md:flex flex-col w-full md:w-[300px] border-r border-gray-700 bg-[#111] max-h-[40vh] md:max-h-none overflow-hidden`}
      >
        <div className="hidden md:flex px-4 py-2 border-b border-gray-700 items-center justify-between">
          <button
            onClick={() => router.push("/")}
            className="text-blue-500 text-sm hover:underline"
          >
            ← All runs
          </button>
          <button
            onClick={toggleSelectMode}
            className={`text-xs px-2 py-0.5 rounded border ${
              selectMode
                ? "border-red-500 text-red-400"
                : "border-gray-600 text-gray-400 hover:border-gray-500"
            }`}
          >
            {selectMode ? "Cancel" : "Select"}
          </button>
        </div>
        <ClipList
          clips={clips}
          selectedId={selectedId}
          onSelect={handleClipSelect}
          filter={filter}
          onFilterChange={setFilter}
          selectMode={selectMode}
          selectedIds={bulkSelectedIds}
          onToggleSelect={handleToggleBulkSelect}
        />
        {selectMode && bulkSelectedIds.size > 0 && (
          <div className="px-4 py-2 border-t border-gray-700 bg-[#111]">
            <button
              onClick={handleBulkDiscard}
              className="w-full py-1.5 text-sm rounded bg-red-900 hover:bg-red-800 text-white font-medium"
            >
              Discard {bulkSelectedIds.size} selected
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        <SessionStats
          sessionDoneCount={sessionDoneCount}
          sessionStartMs={sessionStartRef.current}
          pendingCount={pendingCount}
        />
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
    </div>
  );
}
