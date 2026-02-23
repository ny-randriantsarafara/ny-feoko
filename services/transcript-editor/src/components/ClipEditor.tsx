"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { Tables } from "@/lib/supabase/types";
import { useShortcutLabels } from "@/hooks/useShortcutLabels";

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
  const { labels } = useShortcutLabels();

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
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-4">
      {/* Header with file name and metadata */}
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
        </div>
      </div>

      {/* Draft transcription reference */}
      {clip.draft_transcription && (
        <div className="p-3 bg-[#1a1a2e] border border-[#2a2a4a] rounded-lg text-sm text-[#a0a0c0] leading-relaxed">
          <span className="text-xs text-gray-500 block mb-1">Draft (Whisper)</span>
          {clip.draft_transcription}
        </div>
      )}

      {/* Audio controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={togglePlay} className="btn">
          {playing ? "Pause" : "Play"}
        </button>
        <button onClick={replay} className="btn">
          Replay
        </button>
        <audio
          ref={audioRef}
          src={audioUrl}
          onEnded={() => setPlaying(false)}
          onPause={() => setPlaying(false)}
          onPlay={() => setPlaying(true)}
          className="flex-1 min-w-0 max-w-full"
          controls
        />
      </div>

      {/* Transcription textarea */}
      <textarea
        ref={textRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type the Malagasy transcription here..."
        className="flex-1 min-h-[150px] md:min-h-[200px] p-4 text-base md:text-lg leading-relaxed font-sans bg-[#1e1e1e] text-gray-200 border border-gray-700 rounded-lg resize-y focus:outline-none focus:border-blue-500"
      />

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row gap-2 sm:justify-between">
        <div className="flex gap-2">
          <button onClick={onPrev} className="btn flex-1 sm:flex-none">
            Prev ({labels.prev})
          </button>
          <button onClick={onNext} className="btn flex-1 sm:flex-none">
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
            onClick={() => handleSave("corrected")}
            disabled={saving}
            className="btn bg-green-800 hover:bg-green-700 font-bold flex-1 sm:flex-none disabled:opacity-50"
          >
            {saving ? "Saving..." : `Save & Next (${labels.save})`}
          </button>
        </div>
      </div>

      {/* Keyboard shortcuts help */}
      <div className="text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1">
        <span>{labels.playPause}: play/pause</span>
        <span>{labels.save}: save & next</span>
        <span>{labels.prev}/{labels.next.replace(/.*?([←→])/, "$1")}: prev/next</span>
        <span>{labels.replay}: replay</span>
        <span>{labels.discard}: discard</span>
      </div>
    </div>
  );
}
