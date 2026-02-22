"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import ClipList from "@/components/ClipList";
import ClipEditor from "@/components/ClipEditor";

interface Clip {
  id: number;
  file_name: string;
  duration_sec: number;
  transcription: string;
  speech_score: number;
  music_score: number;
  corrected: boolean;
  status: "pending" | "corrected" | "discarded";
}

export default function Home() {
  const searchParams = useSearchParams();
  const dir = searchParams.get("dir") || "";

  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchClips = useCallback(async () => {
    if (!dir) return;
    try {
      const res = await fetch(`/api/clips?dir=${encodeURIComponent(dir)}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setClips(data);
      if (data.length > 0 && selectedId === null) {
        setSelectedId(0);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load clips");
    }
  }, [dir, selectedId]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  const selectedClip = clips.find((c) => c.id === selectedId);

  const handleSave = useCallback(
    async (transcription: string, status: "corrected" | "discarded") => {
      if (selectedId === null) return;
      await fetch(`/api/clips/${selectedId}?dir=${encodeURIComponent(dir)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcription, status }),
      });
      // Update local state
      setClips((prev) =>
        prev.map((c) =>
          c.id === selectedId ? { ...c, transcription, status, corrected: true } : c
        )
      );
    },
    [selectedId, dir]
  );

  const goNext = useCallback(() => {
    if (selectedId === null || selectedId >= clips.length - 1) return;
    setSelectedId(selectedId + 1);
  }, [selectedId, clips.length]);

  const goPrev = useCallback(() => {
    if (selectedId === null || selectedId <= 0) return;
    setSelectedId(selectedId - 1);
  }, [selectedId]);

  if (!dir) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <h1>Ambara Transcript Editor</h1>
        <p style={{ color: "#888", marginTop: 16 }}>
          Start with: <code style={{ background: "#222", padding: "4px 8px", borderRadius: 4 }}>
            ./ambara editor --dir data/output/your-run-directory
          </code>
        </p>
      </div>
    );
  }

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
      <ClipList clips={clips} selectedId={selectedId} onSelect={setSelectedId} />
      {selectedClip ? (
        <ClipEditor
          clip={selectedClip}
          audioUrl={`/api/audio/${selectedClip.file_name.replace("clips/", "")}?dir=${encodeURIComponent(dir)}`}
          onSave={handleSave}
          onNext={goNext}
          onPrev={goPrev}
        />
      ) : (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#666" }}>
          Select a clip to start editing
        </div>
      )}
    </div>
  );
}
