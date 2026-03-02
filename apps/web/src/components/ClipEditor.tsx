"use client";

import { useRef, useState, useEffect, useCallback, useMemo } from "react";
import type { Tables } from "@/lib/supabase/types";
import { useShortcutLabels } from "@/hooks/useShortcutLabels";
import { useClipEditorKeyboard } from "@/hooks/useClipEditorKeyboard";
import { useClipEditorAutosave } from "@/hooks/useClipEditorAutosave";
import { wordDiff } from "@/lib/word-diff";
import Waveform from "@/components/Waveform";
import type { WaveformHandle } from "@/components/Waveform";
import { PlaybackSpeedControls } from "@/components/PlaybackSpeedControls";

type Clip = Tables<"clips">;

const JUMP_BACK_SECONDS = 3;

interface ClipEditorProps {
  readonly clip: Clip;
  readonly audioUrl: string;
  readonly onSave: (transcription: string, status: "corrected" | "discarded") => Promise<void>;
  readonly onAutoSave: (transcription: string) => Promise<void>;
  readonly onNext: () => void;
  readonly onPrev: () => void;
  readonly isLastClip: boolean;
  readonly onDiscard?: (transcription: string) => Promise<void>;
  readonly onDirtyChange?: (dirty: boolean) => void;
}

function DiffPanel({
  draft,
  current,
  show,
  onToggle,
}: {
  readonly draft: string;
  readonly current: string;
  readonly show: boolean;
  readonly onToggle: () => void;
}) {
  const segments = useMemo(() => wordDiff(draft, current), [draft, current]);
  const hasChanges = segments.some((s) => s.type !== "equal");

  if (!hasChanges) return null;

  return (
    <div>
      <button
        onClick={onToggle}
        className="text-xs text-gray-400 hover:text-gray-200 transition-colors"
      >
        {show ? "Hide Changes" : "Show Changes"}
      </button>
      {show && (
        <div className="mt-1 p-3 bg-[#1a1a2e] border border-[#2a2a4a] rounded-lg text-sm leading-relaxed max-h-32 overflow-y-auto">
          {segments.map((seg, i) => {
            if (seg.type === "added") {
              return (
                <span key={i} className="bg-green-900/40 text-green-300">
                  {seg.text}
                </span>
              );
            }
            if (seg.type === "removed") {
              return (
                <span key={i} className="bg-red-900/40 text-red-400 line-through">
                  {seg.text}
                </span>
              );
            }
            return <span key={i}>{seg.text}</span>;
          })}
        </div>
      )}
    </div>
  );
}

export default function ClipEditor({ clip, audioUrl, onSave, onAutoSave, onNext, onPrev, isLastClip, onDiscard, onDirtyChange }: ClipEditorProps) {
  const waveformRef = useRef<WaveformHandle>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const originalText = clip.corrected_transcription ?? clip.draft_transcription ?? "";
  const [text, setText] = useState(originalText);
  const [saving, setSaving] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(() => {
    if (typeof window === "undefined") return 1;
    const stored = localStorage.getItem("playback-speed");
    return stored ? Number(stored) : 1;
  });
  const { labels } = useShortcutLabels();

  const isDirty = text !== originalText;
  const { saveStatus, showSaveFlash, clearSaveStatus } = useClipEditorAutosave({
    text,
    isDirty,
    onAutoSave,
    debounceMs: 2000,
  });

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    setText(clip.corrected_transcription ?? clip.draft_transcription ?? "");
    setPlaying(false);
    textRef.current?.focus();
  }, [clip.id, clip.corrected_transcription, clip.draft_transcription]);

  const handleWaveformReady = useCallback(() => {
    waveformRef.current?.play();
  }, []);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const confirmIfDirty = useCallback((): boolean => {
    if (!isDirty) return true;
    return window.confirm("You have unsaved changes. Discard them?");
  }, [isDirty]);

  const togglePlay = useCallback(() => {
    waveformRef.current?.togglePlay();
  }, []);

  const replay = useCallback(() => {
    waveformRef.current?.replay();
  }, []);

  const jumpBack = useCallback(() => {
    waveformRef.current?.jumpBack(JUMP_BACK_SECONDS);
  }, []);

  const changeSpeed = useCallback((newSpeed: number) => {
    setSpeed(newSpeed);
    localStorage.setItem("playback-speed", String(newSpeed));
    waveformRef.current?.setSpeed(newSpeed);
  }, []);

  const handleSave = useCallback(async (status: "corrected" | "discarded" = "corrected") => {
    setSaving(true);
    clearSaveStatus();
    await onSave(text, status);
    setSaving(false);
    if (!isLastClip) {
      onNext();
    }
  }, [text, onSave, onNext, isLastClip, clearSaveStatus]);

  const handleAcceptDraft = useCallback(async () => {
    const draft = clip.draft_transcription ?? "";
    if (!draft) return;
    setSaving(true);
    clearSaveStatus();
    await onSave(draft, "corrected");
    setSaving(false);
    if (!isLastClip) {
      onNext();
    }
  }, [clip.draft_transcription, onSave, onNext, isLastClip, clearSaveStatus]);

  const guardedNext = useCallback(() => {
    if (confirmIfDirty()) onNext();
  }, [confirmIfDirty, onNext]);

  const guardedPrev = useCallback(() => {
    if (confirmIfDirty()) onPrev();
  }, [confirmIfDirty, onPrev]);

  useClipEditorKeyboard({
    handleSave,
    handleAcceptDraft,
    onPrev: guardedPrev,
    onNext: guardedNext,
    onDiscard,
    text,
    speed,
    changeSpeed,
    togglePlay,
    replay,
    jumpBack,
  });

  return (
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-4 overflow-y-auto">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2">
        <h2 className="m-0 font-mono text-base md:text-lg truncate">
          {clip.file_name.replace("clips/", "")}
        </h2>
        <div className="flex flex-wrap gap-2 md:gap-3 text-xs md:text-sm text-gray-400">
          <span>Speech: {((clip.speech_score ?? 0) * 100).toFixed(0)}%</span>
          <span>Music: {((clip.music_score ?? 0) * 100).toFixed(0)}%</span>
          <span>{(clip.duration_sec ?? 0).toFixed(1)}s</span>
          <span
            className={`px-2 py-0.5 rounded text-xs text-white ${
              clip.status === "corrected"
                ? "bg-green-800"
                : clip.status === "discarded"
                ? "bg-red-900"
                : "bg-gray-700"
            }`}
          >
            {clip.status}
          </span>
          {saveStatus === "saving" && <span className="text-yellow-500">Saving...</span>}
          {saveStatus === "error" && <span className="text-red-500">Autosave failed</span>}
          {saveStatus === "saved" && (
            <span className="text-green-400 flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Saved
            </span>
          )}
        </div>
      </div>

      {clip.draft_transcription && (
        <div className="p-3 bg-[#1a1a2e] border border-[#2a2a4a] rounded-lg text-sm text-[#a0a0c0] leading-relaxed">
          <span className="text-xs text-gray-500 block mb-1">Draft (Whisper)</span>
          {clip.draft_transcription}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <Waveform
          ref={waveformRef}
          audioUrl={audioUrl}
          speed={speed}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onFinish={() => setPlaying(false)}
          onReady={handleWaveformReady}
        />
        <div className="flex flex-wrap gap-2 items-center">
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
        </div>
      </div>

      <textarea
        ref={textRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type the Malagasy transcription here..."
        className={`flex-1 min-h-[150px] md:min-h-[200px] p-4 text-base md:text-lg leading-relaxed font-sans bg-[#1e1e1e] text-gray-200 border-2 rounded-lg resize-y focus:outline-none transition-colors duration-300 ${
          showSaveFlash
            ? "border-green-500/70"
            : "border-gray-700 focus:border-blue-500"
        }`}
      />

      {clip.draft_transcription && isDirty && (
        <DiffPanel
          draft={clip.draft_transcription}
          current={text}
          show={showDiff}
          onToggle={() => setShowDiff((v) => !v)}
        />
      )}

      <div className="flex flex-col sm:flex-row flex-wrap gap-2 sm:justify-between">
        <div className="flex flex-wrap gap-2">
          <button onClick={guardedPrev} className="btn flex-1 sm:flex-none">
            Prev ({labels.prev})
          </button>
          <button onClick={guardedNext} className="btn flex-1 sm:flex-none">
            Next ({labels.next})
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              if (onDiscard) {
                onDiscard(text);
              } else {
                handleSave("discarded");
              }
            }}
            className="btn bg-red-900 hover:bg-red-800 flex-1 sm:flex-none"
          >
            Discard ({labels.discard})
          </button>
          <button
            onClick={handleAcceptDraft}
            disabled={saving || !clip.draft_transcription}
            className="btn bg-blue-800 hover:bg-blue-700 flex-1 sm:flex-none disabled:opacity-50"
            title="Accept the Whisper draft as-is"
          >
            Accept Draft ({labels.acceptDraft})
          </button>
          <button
            onClick={() => handleSave("corrected")}
            disabled={saving}
            className="btn bg-green-800 hover:bg-green-700 font-bold flex-1 sm:flex-none disabled:opacity-50"
          >
            {saving ? "Saving..." : `Save & Next (${labels.save})`}
          </button>
        </div>
      </div>

      {isLastClip && clip.status !== "pending" && (
        <div className="text-center text-green-400 text-sm py-2">
          All clips in this run have been processed!
        </div>
      )}

      <div className="text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1">
        <span>{labels.playPause}: play/pause</span>
        <span>{labels.save}: save & next</span>
        <span>{labels.acceptDraft}: accept draft</span>
        <span>{labels.prev}/{labels.next.replace(/.*?([←→])/, "$1")}: prev/next</span>
        <span>{labels.replay}: replay</span>
        <span>{labels.discard}: discard</span>
        <span>Ctrl+B: jump back {JUMP_BACK_SECONDS}s</span>
        <span>Ctrl+↑/↓: speed</span>
      </div>
    </div>
  );
}
