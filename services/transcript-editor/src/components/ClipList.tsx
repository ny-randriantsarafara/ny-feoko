"use client";

import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

interface ClipListProps {
  clips: Clip[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "#6b7280",
  corrected: "#22c55e",
  discarded: "#ef4444",
};

export default function ClipList({ clips, selectedId, onSelect }: ClipListProps) {
  const correctedCount = clips.filter((c) => c.status === "corrected").length;
  const total = clips.length;

  return (
    <div style={{ width: 300, borderRight: "1px solid #333", overflow: "auto", background: "#111" }}>
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #333", position: "sticky", top: 0, background: "#111", zIndex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>
          Clips ({correctedCount}/{total} corrected)
        </div>
        <div style={{ marginTop: 4, height: 4, background: "#333", borderRadius: 2 }}>
          <div
            style={{
              height: "100%",
              width: `${(correctedCount / Math.max(total, 1)) * 100}%`,
              background: "#22c55e",
              borderRadius: 2,
              transition: "width 0.3s",
            }}
          />
        </div>
      </div>
      {clips.map((clip) => (
        <div
          key={clip.id}
          onClick={() => onSelect(clip.id)}
          style={{
            padding: "8px 16px",
            cursor: "pointer",
            background: clip.id === selectedId ? "#1e293b" : "transparent",
            borderLeft: `3px solid ${STATUS_COLORS[clip.status]}`,
            fontSize: 13,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "monospace" }}>
              {clip.file_name.replace("clips/", "")}
            </span>
            <span style={{ color: "#666" }}>{(clip.duration_sec ?? 0).toFixed(1)}s</span>
          </div>
          {(clip.corrected_transcription ?? clip.draft_transcription) && (
            <div style={{ color: "#888", fontSize: 12, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {clip.corrected_transcription ?? clip.draft_transcription}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
