"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { Tables } from "@/lib/supabase/types";
import { useShortcutLabels } from "@/hooks/useShortcutLabels";
import Waveform from "@/components/Waveform";
import type { WaveformHandle } from "@/components/Waveform";

type Clip = Tables<"clips">;

const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;
const JUMP_BACK_SECONDS = 3;
const AUTOSAVE_DELAY_MS = 2000;

interface ClipEditorProps {
  clip: Clip;
  audioUrl: string;
  onSave: (transcription: string, status: "corrected" | "discarded") => Promise<void>;
  onAutoSave: (transcription: string) => Promise<void>;
  onNext: () => void;
  onPrev: () => void;
  isLastClip: boolean;
}

export default function ClipEditor({ clip, audioUrl, onSave, onAutoSave, onNext, onPrev, isLastClip }: ClipEditorProps) {
  const waveformRef = useRef<WaveformHandle>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const originalText = clip.corrected_transcription ?? clip.draft_transcription ?? "";
  const [text, setText] = useState(originalText);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"" | "saving" | "saved">("");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(() => {
    if (typeof window === "undefined") return 1;
    const stored = localStorage.getItem("playback-speed");
    return stored ? Number(stored) : 1;
  });
  const { labels } = useShortcutLabels();

  const isDirty = text !== originalText;

  useEffect(() => {
    setText(clip.corrected_transcription ?? clip.draft_transcription ?? "");
    setSaveStatus("");
    setPlaying(false);
    textRef.current?.focus();
  }, [clip.id, clip.corrected_transcription, clip.draft_transcription]);

  const handleWaveformReady = useCallback(() => {
    waveformRef.current?.play();
  }, []);

  useEffect(() => {
    if (!isDirty) return;

    const timer = setTimeout(() => {
      setSaveStatus("saving");
      onAutoSave(text).then(() => setSaveStatus("saved")).catch(() => setSaveStatus(""));
    }, AUTOSAVE_DELAY_MS);

    return () => clearTimeout(timer);
  }, [text, isDirty, onAutoSave]);

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
    await onSave(text, status);
    setSaving(false);
    setSaveStatus("");
    if (!isLastClip) {
      onNext();
    }
  }, [text, onSave, onNext, isLastClip]);

  const handleAcceptDraft = useCallback(async () => {
    const draft = clip.draft_transcription ?? "";
    if (!draft) return;
    setSaving(true);
    await onSave(draft, "corrected");
    setSaving(false);
    setSaveStatus("");
    if (!isLastClip) {
      onNext();
    }
  }, [clip.draft_transcription, onSave, onNext, isLastClip]);

  const guardedNext = useCallback(() => {
    if (confirmIfDirty()) onNext();
  }, [confirmIfDirty, onNext]);

  const guardedPrev = useCallback(() => {
    if (confirmIfDirty()) onPrev();
  }, [confirmIfDirty, onPrev]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl && e.shiftKey && e.key === "Enter") {
        e.preventDefault();
        handleAcceptDraft();
      } else if (isCtrl && e.key === "Enter") {
        e.preventDefault();
        handleSave("corrected");
      } else if (isCtrl && e.key === "ArrowRight") {
        e.preventDefault();
        guardedNext();
      } else if (isCtrl && e.key === "ArrowLeft") {
        e.preventDefault();
        guardedPrev();
      } else if (isCtrl && e.key === "r") {
        e.preventDefault();
        replay();
      } else if (isCtrl && e.key === "d") {
        e.preventDefault();
        handleSave("discarded");
      } else if (isCtrl && e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (isCtrl && e.key === "b") {
        e.preventDefault();
        jumpBack();
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
  }, [handleSave, handleAcceptDraft, guardedNext, guardedPrev, replay, togglePlay, jumpBack, changeSpeed, speed]);

  return (
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-4">
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
          {saveStatus === "saved" && <span className="text-green-500">Saved</span>}
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
        </div>
      </div>

      <textarea
        ref={textRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type the Malagasy transcription here..."
        className="flex-1 min-h-[150px] md:min-h-[200px] p-4 text-base md:text-lg leading-relaxed font-sans bg-[#1e1e1e] text-gray-200 border border-gray-700 rounded-lg resize-y focus:outline-none focus:border-blue-500"
      />

      <div className="flex flex-col sm:flex-row gap-2 sm:justify-between">
        <div className="flex gap-2">
          <button onClick={guardedPrev} className="btn flex-1 sm:flex-none">
            Prev ({labels.prev})
          </button>
          <button onClick={guardedNext} className="btn flex-1 sm:flex-none">
            Next ({labels.next})
          </button>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleSave("discarded")}
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
