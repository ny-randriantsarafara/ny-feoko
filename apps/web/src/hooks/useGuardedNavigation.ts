"use client";

import { useCallback } from "react";

export type Mode = "transcribe" | "split" | "record";

export interface UseGuardedNavigationParams {
  editorDirtyRef: React.RefObject<boolean>;
  setMode: (mode: Mode) => void;
  setSelectedId: (id: string) => void;
  setSidebarOpen: (open: boolean) => void;
}

export function useGuardedNavigation(params: UseGuardedNavigationParams) {
  const { editorDirtyRef, setMode, setSelectedId, setSidebarOpen } = params;

  const guardedSetMode = useCallback(
    (newMode: Mode) => {
      if (editorDirtyRef.current) {
        const proceed = window.confirm("You have unsaved changes. Discard them?");
        if (!proceed) return;
      }
      setMode(newMode);
    },
    [editorDirtyRef, setMode]
  );

  const guardedSelectClip = useCallback(
    (id: string) => {
      if (editorDirtyRef.current) {
        const proceed = window.confirm("You have unsaved changes. Discard them?");
        if (!proceed) return;
      }
      setSelectedId(id);
      setSidebarOpen(false);
    },
    [editorDirtyRef, setSelectedId, setSidebarOpen]
  );

  return { guardedSetMode, guardedSelectClip };
}
