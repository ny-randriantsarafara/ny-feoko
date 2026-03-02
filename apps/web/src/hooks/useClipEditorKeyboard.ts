"use client";

import { useEffect } from "react";
import { SPEED_OPTIONS } from "@/components/PlaybackSpeedControls";

export interface UseClipEditorKeyboardParams {
  readonly handleSave: (status: "corrected" | "discarded") => void | Promise<void>;
  readonly handleAcceptDraft: () => void | Promise<void>;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly onDiscard?: (text: string) => void | Promise<void>;
  readonly text: string;
  readonly speed: number;
  readonly changeSpeed: (speed: number) => void;
  readonly togglePlay: () => void;
  readonly replay: () => void;
  readonly jumpBack: () => void;
}

/**
 * Keyboard shortcut handling for ClipEditor.
 * Registers global keydown listener and invokes callbacks.
 * Side-effect only; returns nothing.
 */
export function useClipEditorKeyboard(params: UseClipEditorKeyboardParams): void {
  const {
    handleSave,
    handleAcceptDraft,
    onPrev,
    onNext,
    onDiscard,
    text,
    speed,
    changeSpeed,
    togglePlay,
    replay,
    jumpBack,
  } = params;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && e.shiftKey && e.key === "Enter") {
        e.preventDefault();
        void handleAcceptDraft();
      } else if (isCtrl && e.key === "Enter") {
        e.preventDefault();
        void handleSave("corrected");
      } else if (isCtrl && e.key === "ArrowRight") {
        e.preventDefault();
        onNext();
      } else if (isCtrl && e.key === "ArrowLeft") {
        e.preventDefault();
        onPrev();
      } else if (isCtrl && e.key === "r") {
        e.preventDefault();
        replay();
      } else if (isCtrl && e.key === "d") {
        e.preventDefault();
        if (onDiscard) {
          void onDiscard(text);
        } else {
          void handleSave("discarded");
        }
      } else if (isCtrl && e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (isCtrl && e.key === "b") {
        e.preventDefault();
        jumpBack();
      } else if (isCtrl && e.key === "ArrowUp") {
        e.preventDefault();
        const idx = SPEED_OPTIONS.indexOf(speed as (typeof SPEED_OPTIONS)[number]);
        if (idx < SPEED_OPTIONS.length - 1) changeSpeed(SPEED_OPTIONS[idx + 1]);
      } else if (isCtrl && e.key === "ArrowDown") {
        e.preventDefault();
        const idx = SPEED_OPTIONS.indexOf(speed as (typeof SPEED_OPTIONS)[number]);
        if (idx > 0) changeSpeed(SPEED_OPTIONS[idx - 1]);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    handleSave,
    handleAcceptDraft,
    onPrev,
    onNext,
    onDiscard,
    text,
    speed,
    changeSpeed,
    togglePlay,
    replay,
    jumpBack,
  ]);
}
