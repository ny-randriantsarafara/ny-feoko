"use client";

import { useState, useEffect } from "react";
import { getIsMacOS } from "@/lib/platform";

/**
 * Shortcut definitions with platform-specific labels.
 * mac: Uses command glyph (⌘)
 * other: Uses Ctrl prefix
 */
const SHORTCUTS = {
  save: { mac: "⌘Enter", other: "Ctrl+Enter" },
  next: { mac: "⌘→", other: "Ctrl+→" },
  prev: { mac: "⌘←", other: "Ctrl+←" },
  replay: { mac: "⌘R", other: "Ctrl+R" },
  discard: { mac: "⌘D", other: "Ctrl+D" },
  playPause: { mac: "⌘Space", other: "Ctrl+Space" },
};

type ShortcutAction = keyof typeof SHORTCUTS;

export interface ShortcutLabels {
  save: string;
  next: string;
  prev: string;
  replay: string;
  discard: string;
  playPause: string;
}

interface UseShortcutLabelsResult {
  labels: ShortcutLabels;
  isMacOS: boolean;
}

/**
 * Builds shortcut labels for a given platform.
 */
function buildLabels(isMacOS: boolean): ShortcutLabels {
  return {
    save: isMacOS ? SHORTCUTS.save.mac : SHORTCUTS.save.other,
    next: isMacOS ? SHORTCUTS.next.mac : SHORTCUTS.next.other,
    prev: isMacOS ? SHORTCUTS.prev.mac : SHORTCUTS.prev.other,
    replay: isMacOS ? SHORTCUTS.replay.mac : SHORTCUTS.replay.other,
    discard: isMacOS ? SHORTCUTS.discard.mac : SHORTCUTS.discard.other,
    playPause: isMacOS ? SHORTCUTS.playPause.mac : SHORTCUTS.playPause.other,
  };
}

/**
 * Hook that provides platform-aware shortcut labels.
 * Detects platform on mount to avoid SSR hydration mismatch.
 * Returns Ctrl-based labels during SSR and before hydration.
 */
export function useShortcutLabels(): UseShortcutLabelsResult {
  const [isMacOS, setIsMacOS] = useState(false);

  useEffect(() => {
    setIsMacOS(getIsMacOS());
  }, []);

  const labels = buildLabels(isMacOS);

  return { labels, isMacOS };
}

/**
 * Get shortcut label for a specific action.
 * Useful for static contexts where hook cannot be used.
 */
export function getShortcutLabel(
  action: ShortcutAction,
  isMacOS: boolean,
): string {
  return isMacOS ? SHORTCUTS[action].mac : SHORTCUTS[action].other;
}

/**
 * All shortcut definitions for documentation or help text.
 */
export const SHORTCUT_ACTIONS = SHORTCUTS;
