"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

interface ClipEditorProps {
  clip: Clip;
  audioUrl: string;
  onSave: (transcription: string, status: "corrected" | "discarded") => Promise<void>;
  onNext: () => void;
  onPrev: () => void;
}

export default function ClipEditor({ clip, audioUrl, onSave, onNext, onPrev }: ClipEditorProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState(clip.corrected_transcription ?? clip.draft_transcription ?? "");
  const [saving, setSaving] = useState(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setText(clip.corrected_transcription ?? clip.draft_transcription ?? "");
    setPlaying(false);
    audioRef.current?.play().then(() => setPlaying(true)).catch(() => {});
    textRef.current?.focus();
  }, [clip.id, clip.corrected_transcription, clip.draft_transcription]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().then(() => setPlaying(true));
    } else {
      audio.pause();
      setPlaying(false);
    }
  }, []);

  const replay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = 0;
    audio.play().then(() => setPlaying(true));
  }, []);

  const handleSave = useCallback(async (status: "corrected" | "discarded" = "corrected") => {
    setSaving(true);
    await onSave(text, status);
    setSaving(false);
    onNext();
  }, [text, onSave, onNext]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && e.key === "Enter") {
        e.preventDefault();
        handleSave("corrected");
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
        handleSave("discarded");
      } else if (e.key === " " && e.target === document.body) {
        e.preventDefault();
        togglePlay();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSave, onNext, onPrev, replay, togglePlay]);

  return (
    <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontFamily: "monospace", fontSize: 18 }}>
          {clip.file_name.replace("clips/", "")}
        </h2>
        <div style={{ display: "flex", gap: 12, fontSize: 13, color: "#888" }}>
          <span>Speech: {((clip.speech_score ?? 0) * 100).toFixed(0)}%</span>
          <span>Music: {((clip.music_score ?? 0) * 100).toFixed(0)}%</span>
          <span>{(clip.duration_sec ?? 0).toFixed(1)}s</span>
          <span style={{
            padding: "2px 8px",
            borderRadius: 4,
            background: clip.status === "corrected" ? "#166534" : clip.status === "discarded" ? "#7f1d1d" : "#374151",
            color: "white",
            fontSize: 12,
          }}>
            {clip.status}
          </span>
        </div>
      </div>

      {clip.draft_transcription && (
        <div style={{
          padding: 12,
          background: "#1a1a2e",
          border: "1px solid #2a2a4a",
          borderRadius: 8,
          fontSize: 14,
          color: "#a0a0c0",
          lineHeight: 1.5,
        }}>
          <span style={{ fontSize: 11, color: "#666", display: "block", marginBottom: 4 }}>
            Draft (Whisper)
          </span>
          {clip.draft_transcription}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button onClick={togglePlay} style={btnStyle}>
          {playing ? "Pause" : "Play"}
        </button>
        <button onClick={replay} style={btnStyle}>
          Replay
        </button>
        <audio
          ref={audioRef}
          src={audioUrl}
          onEnded={() => setPlaying(false)}
          onPause={() => setPlaying(false)}
          onPlay={() => setPlaying(true)}
          style={{ flex: 1 }}
          controls
        />
      </div>

      <textarea
        ref={textRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type the Malagasy transcription here..."
        style={{
          flex: 1,
          minHeight: 200,
          padding: 16,
          fontSize: 18,
          lineHeight: 1.6,
          fontFamily: "system-ui",
          background: "#1e1e1e",
          color: "#e0e0e0",
          border: "1px solid #333",
          borderRadius: 8,
          resize: "vertical",
        }}
      />

      <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onPrev} style={btnStyle}>
            Prev (Ctrl+←)
          </button>
          <button onClick={onNext} style={btnStyle}>
            Next (Ctrl+→)
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => handleSave("discarded")}
            style={{ ...btnStyle, background: "#7f1d1d" }}
          >
            Discard (Ctrl+D)
          </button>
          <button
            onClick={() => handleSave("corrected")}
            disabled={saving}
            style={{ ...btnStyle, background: "#166534", fontWeight: 700 }}
          >
            {saving ? "Saving..." : "Save & Next (Ctrl+Enter)"}
          </button>
        </div>
      </div>

      <div style={{ fontSize: 12, color: "#555", display: "flex", gap: 16 }}>
        <span>Space: play/pause</span>
        <span>Ctrl+Enter: save & next</span>
        <span>Ctrl+←/→: prev/next</span>
        <span>Ctrl+R: replay</span>
        <span>Ctrl+D: discard</span>
      </div>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "8px 16px",
  background: "#333",
  color: "white",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 13,
};
