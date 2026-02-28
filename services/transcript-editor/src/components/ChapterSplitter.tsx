"use client";

import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import type { ParagraphMeta } from "@/lib/supabase/types";
import { splitWavAtBoundaries } from "@/lib/audio-split";
import { createClient } from "@/lib/supabase/client";

interface ChapterSplitterProps {
  readonly clipId: string;
  readonly runId: string;
  readonly audioUrl: string;
  readonly fileName: string;
  readonly paragraphs: readonly ParagraphMeta[];
  readonly onSplitComplete: () => void;
}

interface SplitPoint {
  readonly id: string;
  readonly audioTime: number;
  readonly textCharIndex: number | null;
}

const MARKER_COLOR = "rgba(255, 165, 0, 0.7)";
const MARKER_WIDTH_SEC = 0.05;
const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;
const JUMP_BACK_SECONDS = 3;
const PARAGRAPH_SEPARATOR = "\n";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function parseTime(input: string): number | null {
  const trimmed = input.trim();

  const colonMatch = trimmed.match(/^(\d+):(\d+(?:\.\d+)?)$/);
  if (colonMatch) {
    const minutes = parseInt(colonMatch[1], 10);
    const secs = parseFloat(colonMatch[2]);
    if (!isNaN(minutes) && !isNaN(secs) && secs < 60) {
      return minutes * 60 + secs;
    }
    return null;
  }

  const plain = parseFloat(trimmed);
  if (!isNaN(plain) && plain >= 0) {
    return plain;
  }

  return null;
}

function snapToWordBoundary(text: string, charIndex: number): number {
  if (charIndex <= 0) return 0;
  if (charIndex >= text.length) return text.length;

  if (text[charIndex] === " " || text[charIndex] === "\n") {
    return charIndex;
  }

  let left = charIndex;
  while (left > 0 && text[left] !== " " && text[left] !== "\n") {
    left--;
  }

  let right = charIndex;
  while (right < text.length && text[right] !== " " && text[right] !== "\n") {
    right++;
  }

  return (charIndex - left <= right - charIndex) ? left : right;
}

function textSnippetAround(text: string, charIndex: number): string {
  const radius = 30;
  const start = Math.max(0, charIndex - radius);
  const end = Math.min(text.length, charIndex + radius);
  const before = (start > 0 ? "..." : "") + text.slice(start, charIndex);
  const after = text.slice(charIndex, end) + (end < text.length ? "..." : "");
  return `${before}|${after}`;
}

let nextPointId = 0;
function createPointId(): string {
  nextPointId += 1;
  return `sp-${nextPointId}`;
}

export default function ChapterSplitter({
  clipId,
  runId,
  audioUrl,
  fileName,
  paragraphs,
  onSplitComplete,
}: ChapterSplitterProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);

  const [splitPoints, setSplitPoints] = useState<SplitPoint[]>([]);
  const [editingPointId, setEditingPointId] = useState<string | null>(null);
  const [editingTimeId, setEditingTimeId] = useState<string | null>(null);
  const [timeInputValue, setTimeInputValue] = useState("");
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [splitting, setSplitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speed, setSpeed] = useState(() => {
    if (typeof window === "undefined") return 1;
    const stored = localStorage.getItem("playback-speed");
    return stored ? Number(stored) : 1;
  });

  const fullText = useMemo(
    () =>
      paragraphs
        .map((p) => (p.heading ? `${p.heading}\n${p.text}` : p.text))
        .join(PARAGRAPH_SEPARATOR),
    [paragraphs],
  );

  const canSplit =
    splitPoints.length >= 1 &&
    splitPoints.every((p) => p.textCharIndex !== null);

  const segmentCount = splitPoints.length + 1;

  useEffect(() => {
    if (!containerRef.current) return;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#4a4a6a",
      progressColor: "#6366f1",
      cursorColor: "#818cf8",
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 128,
      normalize: true,
      plugins: [regions],
    });

    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.on("ready", () => {
      setDuration(ws.getDuration());
      ws.setPlaybackRate(speed, true);
    });

    ws.load(audioUrl);
    wsRef.current = ws;

    return () => {
      ws.destroy();
      wsRef.current = null;
      regionsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl]);

  const changeSpeed = useCallback((newSpeed: number) => {
    setSpeed(newSpeed);
    localStorage.setItem("playback-speed", String(newSpeed));
    wsRef.current?.setPlaybackRate(newSpeed, true);
  }, []);

  const togglePlay = useCallback(() => {
    wsRef.current?.playPause();
  }, []);

  const replay = useCallback(() => {
    const ws = wsRef.current;
    if (!ws) return;
    ws.seekTo(0);
    ws.play();
  }, []);

  const jumpBack = useCallback(() => {
    const ws = wsRef.current;
    if (!ws) return;
    const dur = ws.getDuration();
    if (dur === 0) return;
    const newTime = Math.max(0, ws.getCurrentTime() - JUMP_BACK_SECONDS);
    ws.seekTo(newTime / dur);
    ws.play();
  }, []);

  const addSplitPoint = useCallback(() => {
    const ws = wsRef.current;
    const regions = regionsRef.current;
    if (!ws || !regions) return;

    const time = ws.getCurrentTime();
    const id = createPointId();

    regions.addRegion({
      id,
      start: time,
      end: time + MARKER_WIDTH_SEC,
      color: MARKER_COLOR,
      drag: false,
      resize: false,
    });

    setSplitPoints((prev) => [...prev, { id, audioTime: time, textCharIndex: null }]);
    setEditingPointId(id);
  }, []);

  const removeSplitPoint = useCallback((pointId: string) => {
    const regions = regionsRef.current;
    if (regions) {
      const allRegions = regions.getRegions();
      const region = allRegions.find((r) => r.id === pointId);
      region?.remove();
    }
    setSplitPoints((prev) => prev.filter((p) => p.id !== pointId));
    setEditingPointId((prev) => (prev === pointId ? null : prev));
  }, []);

  const setTextForPoint = useCallback((pointId: string, charIndex: number) => {
    setSplitPoints((prev) =>
      prev.map((p) => (p.id === pointId ? { ...p, textCharIndex: charIndex } : p)),
    );
    setEditingPointId(null);
  }, []);

  const updateAudioTime = useCallback((pointId: string, newTime: number) => {
    const clamped = Math.max(0, Math.min(newTime, duration));
    setSplitPoints((prev) =>
      prev.map((p) => (p.id === pointId ? { ...p, audioTime: clamped } : p)),
    );

    const regions = regionsRef.current;
    if (regions) {
      const allRegions = regions.getRegions();
      const region = allRegions.find((r) => r.id === pointId);
      if (region) {
        region.remove();
        regions.addRegion({
          id: pointId,
          start: clamped,
          end: clamped + MARKER_WIDTH_SEC,
          color: MARKER_COLOR,
          drag: false,
          resize: false,
        });
      }
    }
  }, [duration]);

  const clearAll = useCallback(() => {
    regionsRef.current?.clearRegions();
    setSplitPoints([]);
    setEditingPointId(null);
  }, []);

  const handleSplit = useCallback(async () => {
    if (!canSplit) return;

    setSplitting(true);
    setError(null);

    try {
      const byAudio = [...splitPoints].sort((a, b) => a.audioTime - b.audioTime);
      const audioBoundaries = byAudio.map((p) => p.audioTime);

      const byText = [...splitPoints].sort(
        (a, b) => (a.textCharIndex ?? 0) - (b.textCharIndex ?? 0),
      );
      const textCuts = [
        0,
        ...byText.map((p) => p.textCharIndex ?? 0),
        fullText.length,
      ];

      const response = await fetch(audioUrl);
      const wavBlob = await response.blob();
      const blobs = await splitWavAtBoundaries(wavBlob, audioBoundaries);

      const supabase = createClient();

      const clipRows = Array.from({ length: segmentCount }, (_, index) => ({
        run_id: runId,
        file_name: `chunks/${String(index).padStart(4, "0")}.wav`,
        draft_transcription: fullText.slice(textCuts[index], textCuts[index + 1]).trim(),
        status: "pending" as const,
        priority: segmentCount - index,
      }));

      for (let i = 0; i < blobs.length; i++) {
        const storagePath = `${runId}/${clipRows[i].file_name}`;
        const { error: uploadError } = await supabase.storage
          .from("clips")
          .upload(storagePath, blobs[i], {
            contentType: "audio/wav",
            upsert: true,
          });

        if (uploadError) {
          setError(`Upload failed for chunk ${i + 1}: ${uploadError.message}`);
          setSplitting(false);
          return;
        }
      }

      const { error: insertError } = await supabase
        .from("clips")
        .insert(clipRows);

      if (insertError) {
        setError(`Failed to create clips: ${insertError.message}`);
        setSplitting(false);
        return;
      }

      const originalStoragePath = `${runId}/${fileName}`;
      await supabase.storage.from("clips").remove([originalStoragePath]);
      await supabase.from("clips").delete().eq("id", clipId);

      onSplitComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Split failed");
      setSplitting(false);
    }
  }, [canSplit, splitPoints, fullText, audioUrl, segmentCount, runId, fileName, clipId, onSplitComplete]);

  const playFromTime = useCallback((time: number) => {
    const ws = wsRef.current;
    if (!ws || duration === 0) return;
    ws.seekTo(time / duration);
    ws.play();
  }, [duration]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (editingPointId !== null || editingTimeId !== null) return;

      const isCtrl = e.ctrlKey || e.metaKey;

      if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (isCtrl && e.key === "r") {
        e.preventDefault();
        replay();
      } else if (isCtrl && e.key === "b") {
        e.preventDefault();
        jumpBack();
      } else if (isCtrl && e.key === "m") {
        e.preventDefault();
        addSplitPoint();
      } else if (isCtrl && e.key === "ArrowUp") {
        e.preventDefault();
        const idx = SPEED_OPTIONS.indexOf(speed as typeof SPEED_OPTIONS[number]);
        if (idx < SPEED_OPTIONS.length - 1) changeSpeed(SPEED_OPTIONS[idx + 1]);
      } else if (isCtrl && e.key === "ArrowDown") {
        e.preventDefault();
        const idx = SPEED_OPTIONS.indexOf(speed as typeof SPEED_OPTIONS[number]);
        if (idx > 0) changeSpeed(SPEED_OPTIONS[idx - 1]);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [editingPointId, editingTimeId, togglePlay, replay, jumpBack, addSplitPoint, changeSpeed, speed]);

  const existingTextCuts = useMemo(
    () =>
      splitPoints
        .filter((p) => p.textCharIndex !== null && p.id !== editingPointId)
        .map((p) => p.textCharIndex as number)
        .sort((a, b) => a - b),
    [splitPoints, editingPointId],
  );

  const words = useMemo(() => {
    const result: Array<{ text: string; startIndex: number; isSpace: boolean }> = [];
    let i = 0;
    while (i < fullText.length) {
      if (fullText[i] === " " || fullText[i] === "\n") {
        let j = i;
        while (j < fullText.length && (fullText[j] === " " || fullText[j] === "\n")) {
          j++;
        }
        result.push({ text: fullText.slice(i, j), startIndex: i, isSpace: true });
        i = j;
      } else {
        let j = i;
        while (j < fullText.length && fullText[j] !== " " && fullText[j] !== "\n") {
          j++;
        }
        result.push({ text: fullText.slice(i, j), startIndex: i, isSpace: true });
        i = j;
      }
    }
    return result;
  }, [fullText]);

  const handleWordClick = useCallback(
    (charIndex: number) => {
      if (editingPointId === null) return;
      const snapped = snapToWordBoundary(fullText, charIndex);
      if (snapped <= 0 || snapped >= fullText.length) return;
      setTextForPoint(editingPointId, snapped);
    },
    [editingPointId, fullText, setTextForPoint],
  );

  const sortedForDisplay = useMemo(
    () => [...splitPoints].sort((a, b) => a.audioTime - b.audioTime),
    [splitPoints],
  );

  return (
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-between shrink-0">
        <h2 className="text-base md:text-lg font-medium text-gray-200">
          Split Chapter Audio
        </h2>
        <span className="text-xs text-gray-500">
          {splitPoints.length} split point{splitPoints.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div
        ref={containerRef}
        className="w-full rounded-lg bg-[#1a1a2e] border border-[#2a2a4a] p-2 cursor-pointer shrink-0"
      />

      <div className="flex flex-wrap gap-2 items-center shrink-0">
        <button onClick={togglePlay} className="btn">
          {playing ? "Pause" : "Play"}
        </button>
        <button onClick={replay} className="btn">
          Replay
        </button>
        <button onClick={jumpBack} className="btn" title={`Jump back ${JUMP_BACK_SECONDS}s`}>
          -{JUMP_BACK_SECONDS}s
        </button>
        <div className="flex items-center gap-1 text-xs text-gray-400">
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => changeSpeed(s)}
              className={`px-1.5 py-0.5 rounded text-xs ${
                speed === s ? "bg-blue-700 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
        <div className="w-px h-5 bg-gray-700 mx-1" />
        <button
          onClick={addSplitPoint}
          className="btn bg-orange-800 hover:bg-orange-700"
          title="Add split at current position (Ctrl+M)"
        >
          Add Split Here
        </button>
        <button
          onClick={clearAll}
          disabled={splitPoints.length === 0}
          className="btn bg-gray-800 hover:bg-gray-700 disabled:opacity-40"
        >
          Clear All
        </button>
        <button
          onClick={handleSplit}
          disabled={!canSplit || splitting}
          className="btn bg-green-800 hover:bg-green-700 font-bold disabled:opacity-40"
        >
          {splitting ? "Splitting..." : `Split into ${segmentCount} Clips`}
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-400 shrink-0">{error}</div>
      )}

      <div className="text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1 shrink-0">
        <span>Space: play/pause</span>
        <span>Ctrl+M: add split</span>
        <span>Ctrl+R: replay</span>
        <span>Ctrl+B: back {JUMP_BACK_SECONDS}s</span>
        <span>Ctrl+&uarr;/&darr;: speed</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-3">
        {splitPoints.length === 0 && (
          <div className="text-sm text-gray-500 text-center py-8">
            Play the audio and click &quot;Add Split Here&quot; (or Ctrl+M) where you want to cut.
          </div>
        )}

        {sortedForDisplay.map((point) => {
          const needsText = point.textCharIndex === null;
          const isEditing = editingPointId === point.id;

          return (
            <div key={point.id} className="flex flex-col gap-1">
              <div
                className={`flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors ${
                  isEditing
                    ? "bg-orange-950/30 border-orange-700"
                    : "bg-[#1a1a2e] border-[#2a2a4a]"
                }`}
              >
                {editingTimeId === point.id ? (
                  <form
                    className="shrink-0"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const parsed = parseTime(timeInputValue);
                      if (parsed !== null) {
                        updateAudioTime(point.id, parsed);
                      }
                      setEditingTimeId(null);
                    }}
                  >
                    <input
                      autoFocus
                      value={timeInputValue}
                      onChange={(e) => setTimeInputValue(e.target.value)}
                      onBlur={() => {
                        const parsed = parseTime(timeInputValue);
                        if (parsed !== null) {
                          updateAudioTime(point.id, parsed);
                        }
                        setEditingTimeId(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          setEditingTimeId(null);
                        }
                        e.stopPropagation();
                      }}
                      className="w-16 text-xs font-mono bg-gray-900 border border-blue-600 rounded px-1 py-0.5 text-blue-300 outline-none"
                      placeholder="m:ss.s"
                    />
                  </form>
                ) : (
                  <button
                    onClick={() => playFromTime(point.audioTime)}
                    onDoubleClick={() => {
                      setEditingTimeId(point.id);
                      setTimeInputValue(formatTime(point.audioTime));
                    }}
                    className="text-xs text-blue-400 hover:underline shrink-0 font-mono"
                    title="Click to play, double-click to edit time"
                  >
                    {formatTime(point.audioTime)}
                  </button>
                )}

                <div className="flex-1 min-w-0 text-sm">
                  {needsText ? (
                    <span
                      className={`text-amber-400 ${isEditing ? "" : "cursor-pointer hover:underline"}`}
                      onClick={() => {
                        if (!isEditing) setEditingPointId(point.id);
                      }}
                    >
                      {isEditing
                        ? "Click a word below to set the text break..."
                        : "Click to set text position"}
                    </span>
                  ) : (
                    <span className="text-gray-400 font-mono text-xs truncate block">
                      {textSnippetAround(fullText, point.textCharIndex ?? 0)}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {!needsText && (
                    <button
                      onClick={() => setEditingPointId(isEditing ? null : point.id)}
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        isEditing
                          ? "bg-orange-800 text-white"
                          : "text-gray-500 hover:text-gray-300 hover:bg-gray-800"
                      }`}
                    >
                      {isEditing ? "Cancel" : "Edit"}
                    </button>
                  )}
                  <button
                    onClick={() => removeSplitPoint(point.id)}
                    className="text-xs text-red-500 hover:text-red-400 px-1.5 py-0.5 rounded hover:bg-gray-800"
                  >
                    Remove
                  </button>
                </div>
              </div>

              {isEditing && (
                <div className="rounded-lg border border-orange-800/50 bg-[#111] p-3 max-h-48 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap">
                  {words.map((word, wi) => {
                    const isCut = existingTextCuts.includes(word.startIndex);

                    return (
                      <span key={wi}>
                        {isCut && (
                          <span className="inline-block w-full h-0.5 my-1 bg-orange-500/50 rounded" />
                        )}
                        <span
                          onClick={() => handleWordClick(word.startIndex)}
                          className="cursor-pointer hover:bg-orange-800/30 rounded-sm transition-colors text-gray-300"
                        >
                          {word.text}
                        </span>
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
