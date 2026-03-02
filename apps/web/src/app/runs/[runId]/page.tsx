"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import ClipList from "@/components/ClipList";
import type { StatusFilter } from "@/components/ClipList";
import ClipEditor from "@/components/ClipEditor";
import ChapterSplitter from "@/components/ChapterSplitter";
import ChunkRecorder from "@/components/ChunkRecorder";
import SessionStats from "@/components/SessionStats";
import ToastContainer from "@/components/Toast";
import type { ToastData } from "@/components/Toast";
import { useClipsData, type Clip } from "@/hooks/useClipsData";
import { useAudioUrls } from "@/hooks/useAudioUrls";
import { useClipActions } from "@/hooks/useClipActions";
import {
  useGuardedNavigation,
  type Mode,
} from "@/hooks/useGuardedNavigation";

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

  const { clips, setClips, selectedId, setSelectedId, selectedClip, fetchClips } =
    useClipsData(runId, supabase, setError);

  const filteredClips = useMemo(() => {
    if (filter === "all") return clips;
    return clips.filter((c) => c.status === filter);
  }, [clips, filter]);

  const { currentAudioUrl } = useAudioUrls(
    runId,
    clips,
    filteredClips,
    selectedId,
    supabase
  );

  const addToast = useCallback((toast: ToastData) => {
    setToasts((prev) => [...prev, toast]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const {
    handleSave,
    handleAutoSave,
    handleDiscardWithUndo,
    handleMergeBack,
    handleBulkDiscard,
    editorDirtyRef,
  } = useClipActions({
    clips,
    setClips,
    selectedId,
    userId,
    runId,
    fetchClips,
    setSelectedId,
    addToast,
    supabase,
    filteredClips,
    bulkSelectedIds,
    setBulkSelectedIds,
    setSelectMode,
    setSessionDoneCount,
    setError,
  });

  const { guardedSetMode, guardedSelectClip } = useGuardedNavigation({
    editorDirtyRef,
    setMode,
    setSelectedId,
    setSidebarOpen,
  });

  const handleDirtyChange = useCallback((dirty: boolean) => {
    editorDirtyRef.current = dirty;
  }, []);

  useEffect(() => {
    supabase.auth
      .getUser()
      .then(({ data }) => {
        setUserId(data.user?.id ?? null);
      })
      .catch(() => {
        router.replace("/login");
      });
  }, [supabase, router]);

  useEffect(() => {
    if (selectedClip) {
      setMode(defaultModeForClip(selectedClip));
    }
  }, [selectedClip?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const pendingCount = useMemo(
    () => clips.filter((c) => c.status === "pending").length,
    [clips]
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
  }, [selectedIndex, filteredClips, setSelectedId]);

  const goPrev = useCallback(() => {
    if (selectedIndex <= 0) return;
    setSelectedId(filteredClips[selectedIndex - 1].id);
  }, [selectedIndex, filteredClips, setSelectedId]);

  const isLastClip = selectedIndex === filteredClips.length - 1;

  const handleClipSelect = useCallback(
    (id: string) => {
      guardedSelectClip(id);
    },
    [guardedSelectClip]
  );

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

  const toggleSelectMode = useCallback(() => {
    setSelectMode((prev) => {
      if (prev) {
        setBulkSelectedIds(new Set());
      }
      return !prev;
    });
  }, []);

  const handleRecorded = useCallback(() => {
    setClips((prev) =>
      prev.map((c) =>
        c.id === selectedId ? { ...c, status: "corrected" as const } : c
      )
    );
    setSessionDoneCount((prev) => prev + 1);

    const nextPending = filteredClips.find(
      (c, i) => i > selectedIndex && c.status === "pending"
    );
    if (nextPending) {
      setSelectedId(nextPending.id);
    }
  }, [selectedId, selectedIndex, filteredClips, setClips, setSelectedId]);

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
