"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Tables } from "@/lib/supabase/types";
import ClipList from "@/components/ClipList";
import type { StatusFilter } from "@/components/ClipList";
import ClipEditor from "@/components/ClipEditor";
import ChapterSplitter from "@/components/ChapterSplitter";
import ChunkRecorder from "@/components/ChunkRecorder";
import SessionStats from "@/components/SessionStats";
import ToastContainer from "@/components/Toast";
import type { ToastData } from "@/components/Toast";

type Clip = Tables<"clips">;
type Mode = "transcribe" | "split" | "record";

function defaultModeForClip(clip: Clip): Mode {
  if (clip.paragraphs !== null && clip.paragraphs !== undefined) {
    return "split";
  }
  return "transcribe";
}

export default function RunEditorPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const supabase = createClient();

  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [audioUrls, setAudioUrls] = useState<Record<string, { url: string; fetchedAt: number }>>({});
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [selectMode, setSelectMode] = useState(false);
  const [bulkSelectedIds, setBulkSelectedIds] = useState<Set<string>>(new Set());
  const [sessionDoneCount, setSessionDoneCount] = useState(0);
  const sessionStartRef = useRef(Date.now());
  const [mode, setMode] = useState<Mode>("transcribe");
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const editorDirtyRef = useRef(false);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    editorDirtyRef.current = dirty;
  }, []);

  const guardedSetMode = useCallback((newMode: Mode) => {
    if (editorDirtyRef.current) {
      const proceed = window.confirm("You have unsaved changes. Discard them?");
      if (!proceed) return;
    }
    setMode(newMode);
  }, []);

  const guardedSelectClip = useCallback((id: string) => {
    if (editorDirtyRef.current) {
      const proceed = window.confirm("You have unsaved changes. Discard them?");
      if (!proceed) return;
    }
    setSelectedId(id);
    setSidebarOpen(false);
  }, []);

  const addToast = useCallback((toast: ToastData) => {
    setToasts((prev) => [...prev, toast]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

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

      const lastClipKey = `lastClip-${runId}`;
      const stored = localStorage.getItem(lastClipKey);
      if (stored && sorted.some((c) => c.id === stored)) {
        return stored;
      }

      const firstPending = sorted.find((c) => c.status === "pending");
      return firstPending?.id ?? sorted[0].id;
    });
  }, [runId, supabase]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  const selectedClip = clips.find((c) => c.id === selectedId);

  useEffect(() => {
    if (selectedId && runId) {
      localStorage.setItem(`lastClip-${runId}`, selectedId);
    }
  }, [selectedId, runId]);

  useEffect(() => {
    if (selectedClip) {
      setMode(defaultModeForClip(selectedClip));
    }
  }, [selectedClip?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredClips = useMemo(() => {
    if (filter === "all") return clips;
    return clips.filter((c) => c.status === filter);
  }, [clips, filter]);

  const pendingCount = useMemo(
    () => clips.filter((c) => c.status === "pending").length,
    [clips],
  );

  const URL_MAX_AGE_MS = 50 * 60 * 1000;

  const getAudioUrl = useCallback(async (clip: Clip, forceRefresh = false): Promise<string> => {
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
  }, [runId, supabase, audioUrls]);

  const [currentAudioUrl, setCurrentAudioUrl] = useState("");

  useEffect(() => {
    const selected = clips.find((c) => c.id === selectedId);
    if (!selected) return;

    const cached = audioUrls[selected.id];
    if (cached && Date.now() - cached.fetchedAt < URL_MAX_AGE_MS) {
      setCurrentAudioUrl(cached.url);
    } else {
      getAudioUrl(selected).then(setCurrentAudioUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, clips]);

  useEffect(() => {
    const selectedIdx = filteredClips.findIndex((c) => c.id === selectedId);
    if (selectedIdx < 0) return;

    const upcoming = filteredClips.slice(selectedIdx + 1, selectedIdx + 3);

    for (const clip of upcoming) {
      getAudioUrl(clip).then((url) => {
        if (url) {
          const audio = new Audio(url);
          audio.preload = "auto";
          audio.load();
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    const interval = setInterval(() => {
      const selected = clips.find((c) => c.id === selectedId);
      if (!selected) return;

      const cached = audioUrls[selected.id];
      if (cached && Date.now() - cached.fetchedAt > 45 * 60 * 1000) {
        getAudioUrl(selected, true).then(setCurrentAudioUrl);
      }
    }, 10 * 60 * 1000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, clips]);

  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  const handleSave = useCallback(
    async (transcription: string, status: "corrected" | "discarded") => {
      if (!selectedId || !userId) return;

      const currentClip = clips.find((c) => c.id === selectedId);
      const previousValue = currentClip?.corrected_transcription ?? currentClip?.draft_transcription ?? "";
      const savedClipId = selectedId;
      const savedAt = new Date().toISOString();

      setClips((prev) =>
        prev.map((c) =>
          c.id === savedClipId
            ? {
                ...c,
                corrected_transcription: transcription,
                status,
                corrected_at: savedAt,
                corrected_by: userId,
              }
            : c
        )
      );
      setSessionDoneCount((prev) => prev + 1);

      saveQueueRef.current = saveQueueRef.current.then(async () => {
        const { error: updateError } = await supabase
          .from("clips")
          .update({
            corrected_transcription: transcription,
            status,
            corrected_at: savedAt,
            corrected_by: userId,
          })
          .eq("id", savedClipId);

        if (updateError) {
          addToast({
            id: `save-error-${Date.now()}`,
            message: `Save failed: ${updateError.message}`,
            durationMs: 8000,
            action: {
              label: "Retry",
              onClick: () => { handleSave(transcription, status); },
            },
          });
          return;
        }

        await supabase.from("clip_edits").insert({
          clip_id: savedClipId,
          editor_id: userId,
          field: "corrected_transcription",
          old_value: previousValue,
          new_value: transcription,
        });
      });
    },
    [selectedId, userId, clips, supabase, addToast]
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

  const handleDiscardWithUndo = useCallback(
    async (transcription: string) => {
      if (!selectedId || !userId) return;

      const clipBefore = clips.find((c) => c.id === selectedId);
      if (!clipBefore) return;

      const previousStatus = clipBefore.status;
      const previousTranscription = clipBefore.corrected_transcription;
      const discardedClipId = selectedId;

      setClips((prev) =>
        prev.map((c) =>
          c.id === discardedClipId
            ? {
                ...c,
                corrected_transcription: transcription,
                status: "discarded" as const,
                corrected_at: new Date().toISOString(),
                corrected_by: userId,
              }
            : c
        )
      );
      setSessionDoneCount((prev) => prev + 1);

      const nextPendingIdx = filteredClips.findIndex(
        (c, i) => i > filteredClips.findIndex((fc) => fc.id === selectedId) && c.status === "pending",
      );
      if (nextPendingIdx >= 0) {
        setSelectedId(filteredClips[nextPendingIdx].id);
      }

      const toastId = `discard-${Date.now()}`;
      let undone = false;

      addToast({
        id: toastId,
        message: "Clip discarded.",
        durationMs: 5000,
        action: {
          label: "Undo",
          onClick: () => {
            undone = true;
            setClips((prev) =>
              prev.map((c) =>
                c.id === discardedClipId
                  ? { ...c, status: previousStatus, corrected_transcription: previousTranscription }
                  : c
              )
            );
            setSessionDoneCount((prev) => Math.max(0, prev - 1));
            setSelectedId(discardedClipId);

            supabase
              .from("clips")
              .update({
                status: previousStatus,
                corrected_transcription: previousTranscription,
                corrected_at: clipBefore.corrected_at,
                corrected_by: clipBefore.corrected_by,
              })
              .eq("id", discardedClipId)
              .then();
          },
        },
      });

      setTimeout(async () => {
        if (undone) return;
        await supabase
          .from("clips")
          .update({
            corrected_transcription: transcription,
            status: "discarded" as const,
            corrected_at: new Date().toISOString(),
            corrected_by: userId,
          })
          .eq("id", discardedClipId);

        await supabase.from("clip_edits").insert({
          clip_id: discardedClipId,
          editor_id: userId,
          field: "corrected_transcription",
          old_value: previousTranscription ?? "",
          new_value: transcription,
        });
      }, 5500);
    },
    [selectedId, userId, clips, filteredClips, supabase, addToast]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      if (!isCtrl) return;

      if (e.key === "1") {
        e.preventDefault();
        guardedSetMode("transcribe");
      } else if (e.key === "2") {
        e.preventDefault();
        guardedSetMode("split");
      } else if (e.key === "3") {
        e.preventDefault();
        guardedSetMode("record");
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [guardedSetMode]);

  const selectedIndex = filteredClips.findIndex((c) => c.id === selectedId);

  const goNext = useCallback(() => {
    if (selectedIndex < 0 || selectedIndex >= filteredClips.length - 1) return;
    setSelectedId(filteredClips[selectedIndex + 1].id);
  }, [selectedIndex, filteredClips]);

  const goPrev = useCallback(() => {
    if (selectedIndex <= 0) return;
    setSelectedId(filteredClips[selectedIndex - 1].id);
  }, [selectedIndex, filteredClips]);

  const isLastClip = selectedIndex === filteredClips.length - 1;

  const handleClipSelect = useCallback((id: string) => {
    guardedSelectClip(id);
  }, [guardedSelectClip]);

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

  const handleMergeBack = useCallback(async (originClipId: string) => {
    const originClip = clips.find((c) => c.id === originClipId);
    if (!originClip || !originClip.corrected_transcription) return;

    let splitData: { childFileNames: string[]; archivePath: string };
    try {
      splitData = JSON.parse(originClip.corrected_transcription);
      if (!splitData.childFileNames || !splitData.archivePath) return;
    } catch {
      return;
    }

    const childClips = clips.filter((c) =>
      splitData.childFileNames.includes(c.file_name),
    );
    const hasEditedChildren = childClips.some((c) => c.status === "corrected");
    if (hasEditedChildren) {
      addToast({
        id: `merge-blocked-${Date.now()}`,
        message: "Cannot merge: some child clips have been corrected.",
        durationMs: 5000,
      });
      return;
    }

    const originalStoragePath = `${runId}/${originClip.file_name}`;
    const { error: copyError } = await supabase.storage
      .from("clips")
      .copy(splitData.archivePath, originalStoragePath);

    if (copyError) {
      addToast({
        id: `merge-error-${Date.now()}`,
        message: `Merge failed: ${copyError.message}`,
        durationMs: 5000,
      });
      return;
    }

    await supabase
      .from("clips")
      .update({
        status: "pending" as const,
        corrected_transcription: null,
        corrected_at: null,
        corrected_by: null,
      })
      .eq("id", originClipId);

    const childIds = childClips.map((c) => c.id);
    if (childIds.length > 0) {
      const childPaths = childClips.map((c) => `${runId}/${c.file_name}`);
      await supabase.storage.from("clips").remove(childPaths);
      await supabase.from("clips").delete().in("id", childIds);
    }

    await supabase.storage.from("clips").remove([splitData.archivePath]);

    addToast({
      id: `merge-done-${Date.now()}`,
      message: "Clips merged back successfully.",
      durationMs: 3000,
    });

    fetchClips();
  }, [clips, runId, supabase, addToast, fetchClips]);

  const handleRecorded = useCallback(() => {
    setClips((prev) =>
      prev.map((c) =>
        c.id === selectedId ? { ...c, status: "corrected" as const } : c
      )
    );
    setSessionDoneCount((prev) => prev + 1);

    const nextPending = filteredClips.find(
      (c, i) => i > selectedIndex && c.status === "pending",
    );
    if (nextPending) {
      setSelectedId(nextPending.id);
    }
  }, [selectedId, selectedIndex, filteredClips]);

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
          onMergeBack={handleMergeBack}
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

        {selectedClip && (
          <div className="flex border-b border-gray-700 bg-[#111] shrink-0">
            {(["transcribe", "split", "record"] as const).map((m) => (
              <button
                key={m}
                onClick={() => guardedSetMode(m)}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  mode === m
                    ? "text-white border-b-2 border-blue-500"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {m === "transcribe" ? "Transcribe" : m === "split" ? "Split" : "Record"}
              </button>
            ))}
          </div>
        )}

        {selectedClip ? (
          mode === "split" ? (
            <ChapterSplitter
              clipId={selectedClip.id}
              runId={runId}
              audioUrl={currentAudioUrl}
              fileName={selectedClip.file_name}
              paragraphs={selectedClip.paragraphs ?? []}
              onSplitComplete={fetchClips}
            />
          ) : mode === "record" ? (
            <ChunkRecorder
              clip={selectedClip}
              runId={runId}
              onRecorded={handleRecorded}
            />
          ) : (
            <ClipEditor
              clip={selectedClip}
              audioUrl={currentAudioUrl}
              onSave={handleSave}
              onAutoSave={handleAutoSave}
              onNext={goNext}
              onPrev={goPrev}
              isLastClip={isLastClip}
              onDiscard={handleDiscardWithUndo}
              onDirtyChange={handleDirtyChange}
            />
          )
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            {clips.length === 0 ? "Loading clips..." : "Select a clip to start editing"}
          </div>
        )}
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
