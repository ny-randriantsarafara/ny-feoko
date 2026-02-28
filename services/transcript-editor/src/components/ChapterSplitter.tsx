"use client";

import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import Minimap from "wavesurfer.js/dist/plugins/minimap.esm.js";
import type { ParagraphMeta } from "@/lib/supabase/types";
import { formatTime, parseTime } from "@/lib/format";
import { splitWavAtBoundaries, detectSilences } from "@/lib/audio-split";
import type { SilenceRegion } from "@/lib/audio-split";
import { createClient } from "@/lib/supabase/client";
import {
  PlaybackSpeedControls,
  SPEED_OPTIONS,
} from "@/components/PlaybackSpeedControls";

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

type ChunkUploadStatus = "idle" | "uploading" | "uploaded" | "failed";

interface ChunkUploadState {
  readonly index: number;
  readonly status: ChunkUploadStatus;
  readonly error?: string;
}

const MARKER_COLOR = "rgba(255, 165, 0, 0.7)";
const SILENCE_MARKER_COLOR = "rgba(100, 149, 237, 0.3)";
const MARKER_WIDTH_SEC = 0.05;
const JUMP_BACK_SECONDS = 3;
const PARAGRAPH_SEPARATOR = "\n";

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
  const [currentTime, setCurrentTime] = useState(0);
  const [splitting, setSplitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [silenceRegions, setSilenceRegions] = useState<SilenceRegion[]>([]);
  const [chunkUploads, setChunkUploads] = useState<ChunkUploadState[]>([]);
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

  const previewSegments = useMemo(() => {
    if (!canSplit) return [];

    const byAudio = [...splitPoints].sort((a, b) => a.audioTime - b.audioTime);
    const audioBounds = [0, ...byAudio.map((p) => p.audioTime), duration];

    const byText = [...splitPoints].sort(
      (a, b) => (a.textCharIndex ?? 0) - (b.textCharIndex ?? 0),
    );
    const textCuts = [0, ...byText.map((p) => p.textCharIndex ?? 0), fullText.length];

    return Array.from({ length: segmentCount }, (_, i) => {
      const chunkDuration = audioBounds[i + 1] - audioBounds[i];
      const chunkText = fullText.slice(textCuts[i], textCuts[i + 1]).trim();
      return {
        index: i,
        duration: chunkDuration,
        textPreview: chunkText.length > 100 ? chunkText.slice(0, 100) + "..." : chunkText,
        isSuspicious: chunkDuration < 2 || chunkText.length === 0,
      };
    });
  }, [canSplit, splitPoints, duration, fullText, segmentCount]);

  // Text-audio sync: estimate char position from current playback time
  const estimatedCharIndex = useMemo(() => {
    if (duration === 0 || fullText.length === 0) return 0;
    return Math.round((currentTime / duration) * fullText.length);
  }, [currentTime, duration, fullText]);

  useEffect(() => {
    if (!containerRef.current) return;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const minimap = Minimap.create({
      height: 24,
      waveColor: "#3a3a5a",
      progressColor: "#4f46e5",
      cursorColor: "#818cf8",
      cursorWidth: 1,
      barWidth: 1,
      barGap: 0,
      barRadius: 0,
      normalize: true,
    });

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
      plugins: [regions, minimap],
    });

    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.on("ready", () => {
      setDuration(ws.getDuration());
      ws.setPlaybackRate(speed, true);

      // Silence detection
      const backend = ws.getDecodedData();
      if (backend) {
        const detected = detectSilences(backend);
        setSilenceRegions(detected);

        for (const region of detected.slice(0, 20)) {
          regions.addRegion({
            start: region.start,
            end: region.end,
            color: SILENCE_MARKER_COLOR,
            drag: false,
            resize: false,
          });
        }
      }
    });
    ws.on("timeupdate", (time: number) => setCurrentTime(time));

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
    const regions = regionsRef.current;
    if (regions) {
      const allRegions = regions.getRegions();
      for (const r of allRegions) {
        const isSilenceMarker = splitPoints.every((sp) => sp.id !== r.id);
        if (!isSilenceMarker) {
          r.remove();
        }
      }
    }
    setSplitPoints([]);
    setEditingPointId(null);
  }, [splitPoints]);

  const autoSuggestSplits = useCallback(() => {
    const regions = regionsRef.current;
    if (!regions || silenceRegions.length === 0) return;

    clearAll();

    const desiredSplits = Math.max(1, paragraphs.length - 1);
    const candidates = silenceRegions.slice(0, desiredSplits);

    const newPoints: SplitPoint[] = candidates
      .sort((a, b) => a.midpoint - b.midpoint)
      .map((silence) => {
        const id = createPointId();
        regions.addRegion({
          id,
          start: silence.midpoint,
          end: silence.midpoint + MARKER_WIDTH_SEC,
          color: MARKER_COLOR,
          drag: false,
          resize: false,
        });
        return { id, audioTime: silence.midpoint, textCharIndex: null };
      });

    setSplitPoints(newPoints);
    if (newPoints.length > 0) {
      setEditingPointId(newPoints[0].id);
    }
  }, [silenceRegions, paragraphs.length, clearAll]);

  const handleSplit = useCallback(async (retryFromIndex = 0) => {
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
      if (!response.ok) {
        throw new Error(`Failed to fetch audio: ${response.status}`);
      }
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

      const initialUploads: ChunkUploadState[] = blobs.map((_, i) => ({
        index: i,
        status: i < retryFromIndex ? "uploaded" : "idle",
      }));
      setChunkUploads(initialUploads);

      for (let i = retryFromIndex; i < blobs.length; i++) {
        setChunkUploads((prev) =>
          prev.map((u) => (u.index === i ? { ...u, status: "uploading" } : u)),
        );

        const storagePath = `${runId}/${clipRows[i].file_name}`;
        const { error: uploadError } = await supabase.storage
          .from("clips")
          .upload(storagePath, blobs[i], {
            contentType: "audio/wav",
            upsert: true,
          });

        if (uploadError) {
          setChunkUploads((prev) =>
            prev.map((u) =>
              u.index === i ? { ...u, status: "failed", error: uploadError.message } : u,
            ),
          );
          setError(`Upload failed for chunk ${i + 1}: ${uploadError.message}`);
          setSplitting(false);
          return;
        }

        setChunkUploads((prev) =>
          prev.map((u) => (u.index === i ? { ...u, status: "uploaded" } : u)),
        );
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
      const archivePath = `${runId}/_originals/${fileName}`;
      await supabase.storage.from("clips").copy(originalStoragePath, archivePath);
      await supabase.storage.from("clips").remove([originalStoragePath]);

      await supabase
        .from("clips")
        .update({
          status: "discarded" as const,
          corrected_transcription: JSON.stringify({
            _splitOrigin: true,
            childFileNames: clipRows.map((r) => r.file_name),
            archivePath,
            splitAt: new Date().toISOString(),
          }),
        })
        .eq("id", clipId);

      onSplitComplete();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Split failed");
      setSplitting(false);
    }
  }, [canSplit, splitPoints, fullText, audioUrl, segmentCount, runId, fileName, clipId, onSplitComplete]);

  const retryFailedUploads = useCallback(() => {
    const firstFailed = chunkUploads.find((u) => u.status === "failed");
    if (firstFailed) {
      handleSplit(firstFailed.index);
    }
  }, [chunkUploads, handleSplit]);

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
        result.push({ text: fullText.slice(i, j), startIndex: i, isSpace: false });
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

  const uploadedCount = chunkUploads.filter((u) => u.status === "uploaded").length;
  const hasFailed = chunkUploads.some((u) => u.status === "failed");

  return (
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-between shrink-0">
        <h2 className="text-base md:text-lg font-medium text-gray-200">
          Split Chapter Audio
        </h2>
        <div className="flex items-center gap-3">
          {silenceRegions.length > 0 && (
            <span className="text-xs text-blue-400">
              {silenceRegions.length} silence{silenceRegions.length !== 1 ? "s" : ""} detected
            </span>
          )}
          <span className="text-xs text-gray-500">
            {splitPoints.length} split point{splitPoints.length !== 1 ? "s" : ""}
          </span>
        </div>
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
        <PlaybackSpeedControls speed={speed} onSpeedChange={changeSpeed} />
        <div className="w-px h-5 bg-gray-700 mx-1" />
        <button
          onClick={addSplitPoint}
          className="btn bg-orange-800 hover:bg-orange-700"
          title="Add split at current position (Ctrl+M)"
        >
          Add Split Here
        </button>
        {silenceRegions.length > 0 && (
          <button
            onClick={autoSuggestSplits}
            className="btn bg-blue-800 hover:bg-blue-700"
            title="Auto-place splits at detected silences"
          >
            Auto-Split
          </button>
        )}
        <button
          onClick={clearAll}
          disabled={splitPoints.length === 0}
          className="btn bg-gray-800 hover:bg-gray-700 disabled:opacity-40"
        >
          Clear All
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-400 shrink-0 flex items-center gap-2">
          <span>{error}</span>
          {hasFailed && (
            <button
              onClick={retryFailedUploads}
              className="btn bg-orange-800 hover:bg-orange-700 text-xs"
            >
              Retry Failed
            </button>
          )}
        </div>
      )}

      {chunkUploads.length > 0 && splitting && (
        <div className="shrink-0">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>{uploadedCount}/{chunkUploads.length} chunks uploaded</span>
          </div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-600 rounded-full transition-all duration-300"
              style={{ width: `${(uploadedCount / chunkUploads.length) * 100}%` }}
            />
          </div>
          <div className="flex gap-1 mt-1">
            {chunkUploads.map((u) => (
              <div
                key={u.index}
                className={`flex-1 h-1 rounded-full ${
                  u.status === "uploaded"
                    ? "bg-green-600"
                    : u.status === "uploading"
                      ? "bg-blue-500 animate-pulse"
                      : u.status === "failed"
                        ? "bg-red-500"
                        : "bg-gray-700"
                }`}
                title={`Chunk ${u.index + 1}: ${u.status}${u.error ? ` - ${u.error}` : ""}`}
              />
            ))}
          </div>
        </div>
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
            {silenceRegions.length > 0 && (
              <span className="block mt-2 text-blue-400">
                Or click &quot;Auto-Split&quot; to place splits at detected silences.
              </span>
            )}
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
                    const isNearPlayhead =
                      playing &&
                      !word.isSpace &&
                      word.startIndex <= estimatedCharIndex &&
                      (words[wi + 1]?.startIndex ?? fullText.length) > estimatedCharIndex;

                    return (
                      <span key={wi}>
                        {isCut && (
                          <span className="inline-block w-full h-0.5 my-1 bg-orange-500/50 rounded" />
                        )}
                        <span
                          onClick={() => handleWordClick(word.startIndex)}
                          className={`cursor-pointer rounded-sm transition-colors ${
                            isNearPlayhead
                              ? "bg-blue-700/40 text-white"
                              : "hover:bg-orange-800/30 text-gray-300"
                          }`}
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

        {canSplit && (
          <div className="mt-2 shrink-0">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className="text-xs text-gray-400 hover:text-gray-200 transition-colors"
            >
              {showPreview ? "Hide Preview" : "Show Preview"} ({segmentCount} chunks)
            </button>

            {showPreview && (
              <div className="mt-2 flex flex-col gap-1.5">
                {previewSegments.map((seg) => (
                  <div
                    key={seg.index}
                    className={`px-3 py-2 rounded-lg border text-xs ${
                      seg.isSuspicious
                        ? "bg-red-950/30 border-red-800/50"
                        : "bg-[#1a1a2e] border-[#2a2a4a]"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-mono text-gray-400">#{seg.index + 1}</span>
                      <span className="text-gray-500">{seg.duration.toFixed(1)}s</span>
                      {seg.isSuspicious && (
                        <span className="text-amber-400" title="Suspiciously short or empty">
                          ⚠
                        </span>
                      )}
                    </div>
                    <div className="text-gray-400 truncate">{seg.textPreview || "(empty)"}</div>
                  </div>
                ))}

                <button
                  onClick={() => handleSplit()}
                  disabled={!canSplit || splitting}
                  className="btn bg-green-800 hover:bg-green-700 font-bold disabled:opacity-40 mt-1"
                >
                  {splitting ? "Splitting..." : `Split into ${segmentCount} Clips`}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
