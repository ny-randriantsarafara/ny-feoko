"use client";

import { useState, useEffect, useCallback } from "react";

export type AutosaveStatus = "" | "saving" | "saved" | "error";

export interface UseClipEditorAutosaveParams {
  readonly text: string;
  readonly isDirty: boolean;
  readonly onAutoSave: (text: string) => Promise<void>;
  readonly debounceMs?: number;
}

const SAVE_FLASH_DURATION_MS = 1500;

/**
 * Autosave with debounce for ClipEditor.
 * Returns saveStatus, showSaveFlash, and clearSaveStatus for UI feedback.
 * Resets saveStatus when isDirty becomes false (e.g. clip change after save).
 * Use clearSaveStatus when manually saving to clear autosave UI state.
 */
export function useClipEditorAutosave(params: UseClipEditorAutosaveParams): {
  saveStatus: AutosaveStatus;
  showSaveFlash: boolean;
  clearSaveStatus: () => void;
} {
  const { text, isDirty, onAutoSave, debounceMs = 2000 } = params;

  const [saveStatus, setSaveStatus] = useState<AutosaveStatus>("");
  const [showSaveFlash, setShowSaveFlash] = useState(false);

  // Reset save status when no longer dirty (e.g. switched clip after save)
  useEffect(() => {
    if (!isDirty) {
      setSaveStatus("");
    }
  }, [isDirty]);

  useEffect(() => {
    if (!isDirty) return;

    const timer = setTimeout(() => {
      setSaveStatus("saving");
      onAutoSave(text)
        .then(() => {
          setSaveStatus("saved");
          setShowSaveFlash(true);
          setTimeout(() => setShowSaveFlash(false), SAVE_FLASH_DURATION_MS);
        })
        .catch(() => {
          setSaveStatus("error");
        });
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [text, isDirty, onAutoSave, debounceMs]);

  const clearSaveStatus = useCallback(() => {
    setSaveStatus("");
  }, []);

  return { saveStatus, showSaveFlash, clearSaveStatus };
}
