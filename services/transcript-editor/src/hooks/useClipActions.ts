"use client";

import { useCallback, useRef } from "react";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Clip } from "./useClipsData";
import type { ToastData } from "@/components/Toast";

export interface UseClipActionsParams {
  clips: Clip[];
  setClips: React.Dispatch<React.SetStateAction<Clip[]>>;
  selectedId: string | null;
  userId: string | null;
  runId: string | undefined;
  fetchClips: () => Promise<void>;
  setSelectedId: (id: string) => void;
  addToast: (toast: ToastData) => void;
  supabase: SupabaseClient;
  filteredClips: Clip[];
  bulkSelectedIds: Set<string>;
  setBulkSelectedIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  setSelectMode: React.Dispatch<React.SetStateAction<boolean>>;
  setSessionDoneCount: React.Dispatch<React.SetStateAction<number>>;
  setError: (error: string | null) => void;
}

export function useClipActions(params: UseClipActionsParams) {
  const {
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
  } = params;

  const editorDirtyRef = useRef(false);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  const handleSave = useCallback(
    async (transcription: string, status: "corrected" | "discarded") => {
      if (!selectedId || !userId) return;

      const currentClip = clips.find((c) => c.id === selectedId);
      const previousValue =
        currentClip?.corrected_transcription ?? currentClip?.draft_transcription ?? "";
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
              onClick: () => {
                handleSave(transcription, status);
              },
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
    [selectedId, userId, clips, supabase, addToast, setClips, setSessionDoneCount]
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
          c.id === selectedId ? { ...c, corrected_transcription: transcription } : c
        )
      );
    },
    [selectedId, userId, supabase, setClips]
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
        (c, i) =>
          i > filteredClips.findIndex((fc) => fc.id === selectedId) &&
          c.status === "pending"
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
                  ? {
                      ...c,
                      status: previousStatus,
                      corrected_transcription: previousTranscription,
                    }
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
    [
      selectedId,
      userId,
      clips,
      filteredClips,
      supabase,
      addToast,
      setClips,
      setSelectedId,
      setSessionDoneCount,
    ]
  );

  const handleMergeBack = useCallback(
    async (originClipId: string) => {
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
        splitData.childFileNames.includes(c.file_name)
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
    },
    [clips, runId, supabase, addToast, fetchClips]
  );

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
          ? {
              ...c,
              status: "discarded" as const,
              corrected_at: new Date().toISOString(),
              corrected_by: userId,
            }
          : c
      )
    );

    setSessionDoneCount((prev) => prev + ids.length);
    setBulkSelectedIds(new Set());
    setSelectMode(false);
  }, [
    bulkSelectedIds,
    userId,
    supabase,
    setClips,
    setSessionDoneCount,
    setBulkSelectedIds,
    setSelectMode,
    setError,
  ]);

  return {
    handleSave,
    handleAutoSave,
    handleDiscardWithUndo,
    handleMergeBack,
    handleBulkDiscard,
    editorDirtyRef,
  };
}
