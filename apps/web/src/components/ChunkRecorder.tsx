"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { createClient } from "@/lib/supabase/client";
import type { Tables } from "@/lib/supabase/types";

type Clip = Tables<"clips">;

interface ChunkRecorderProps {
  readonly clip: Clip;
  readonly runId: string;
  readonly onRecorded: () => void;
}

type Phase = "idle" | "recording" | "reviewing" | "uploading";

export default function ChunkRecorder({
  clip,
  runId,
  onRecorded,
}: ChunkRecorderProps) {
  const recorder = useAudioRecorder();
  const [phase, setPhase] = useState<Phase>("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const chunkText = clip.draft_transcription ?? "";

  const previewUrl = useMemo(() => {
    if (!recorder.wavBlob) return null;
    return URL.createObjectURL(recorder.wavBlob);
  }, [recorder.wavBlob]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    setPhase("idle");
    setUploadError(null);
    setElapsedSec(0);
    recorder.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip.id]);

  useEffect(() => {
    if (phase !== "recording") {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    setElapsedSec(0);
    timerRef.current = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [phase]);

  useEffect(() => {
    if (!recorder.isRecording && recorder.wavBlob) {
      setPhase("reviewing");
    }
  }, [recorder.isRecording, recorder.wavBlob]);

  const handleRecord = useCallback(async () => {
    setUploadError(null);
    setPhase("recording");
    await recorder.startRecording();
  }, [recorder]);

  const handleStop = useCallback(() => {
    recorder.stopRecording();
  }, [recorder]);

  const handleReRecord = useCallback(() => {
    recorder.reset();
    setPhase("idle");
  }, [recorder]);

  const handleConfirm = useCallback(async () => {
    if (!recorder.wavBlob) return;

    setPhase("uploading");
    setUploadError(null);

    const supabase = createClient();
    const storagePath = `${runId}/${clip.file_name}`;

    const { error: storageError } = await supabase.storage
      .from("clips")
      .upload(storagePath, recorder.wavBlob, {
        contentType: "audio/wav",
        upsert: true,
      });

    if (storageError) {
      setUploadError(storageError.message);
      setPhase("reviewing");
      return;
    }

    const { error: dbError } = await supabase
      .from("clips")
      .update({
        corrected_transcription: chunkText,
        status: "corrected" as const,
        duration_sec: recorder.durationSec,
      })
      .eq("id", clip.id);

    if (dbError) {
      setUploadError(dbError.message);
      setPhase("reviewing");
      return;
    }

    onRecorded();
  }, [recorder.wavBlob, recorder.durationSec, runId, clip.file_name, clip.id, chunkText, onRecorded]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === " ") {
        e.preventDefault();
        if (phase === "idle") {
          handleRecord();
        } else if (phase === "recording") {
          handleStop();
        } else if (phase === "reviewing" && audioRef.current) {
          audioRef.current.currentTime = 0;
          audioRef.current.play();
        }
      } else if (e.key === "Enter" && phase === "reviewing") {
        e.preventDefault();
        handleConfirm();
      } else if (e.key === "Escape" && phase === "reviewing") {
        e.preventDefault();
        handleReRecord();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, handleRecord, handleStop, handleConfirm, handleReRecord]);

  const formatTime = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  };

  return (
    <div className="flex-1 p-4 md:p-6 flex flex-col gap-6 overflow-hidden">
      <div className="flex items-center justify-between shrink-0">
        <span className="text-xs font-mono text-gray-500 truncate">
          {clip.file_name}
        </span>
        <span
          className={`shrink-0 px-2 py-0.5 rounded text-xs text-white ${
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

      <div className="flex-1 flex items-center justify-center overflow-y-auto min-h-0">
        <p className="text-xl md:text-2xl leading-relaxed text-gray-100 text-center max-w-2xl">
          {chunkText}
        </p>
      </div>

      {recorder.error && (
        <div className="text-sm text-red-400 text-center shrink-0">{recorder.error}</div>
      )}
      {uploadError && (
        <div className="text-sm text-red-400 text-center shrink-0">{uploadError}</div>
      )}

      <div className="shrink-0">
        {phase === "idle" && (
          <div className="flex justify-center">
            <button
              onClick={handleRecord}
              className="px-8 py-3 rounded-full bg-red-700 hover:bg-red-600 text-white font-medium text-lg transition-colors"
            >
              Record
            </button>
          </div>
        )}

        {phase === "recording" && (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-2 text-red-400">
              <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
              <span className="font-mono text-lg">{formatTime(elapsedSec)}</span>
            </div>
            <button
              onClick={handleStop}
              className="px-8 py-3 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-medium text-lg transition-colors"
            >
              Done
            </button>
          </div>
        )}

        {phase === "reviewing" && previewUrl && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex items-center gap-3 text-sm text-gray-400">
              <span className="font-mono">{recorder.durationSec.toFixed(1)}s</span>
              <button
                onClick={() => {
                  if (audioRef.current) {
                    audioRef.current.currentTime = 0;
                    audioRef.current.play();
                  }
                }}
                className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
              >
                Play
              </button>
              <audio ref={audioRef} src={previewUrl} />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleReRecord}
                className="px-6 py-2.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium transition-colors"
              >
                Re-record
              </button>
              <button
                onClick={handleConfirm}
                className="px-6 py-2.5 rounded bg-green-800 hover:bg-green-700 text-white font-medium transition-colors"
              >
                Confirm & Next
              </button>
            </div>
          </div>
        )}

        {phase === "uploading" && (
          <div className="flex justify-center">
            <span className="text-gray-400 text-sm">Uploading...</span>
          </div>
        )}

        <div className="text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1 justify-center mt-2">
          <span>Space: {phase === "idle" ? "record" : phase === "recording" ? "stop" : "play"}</span>
          {phase === "reviewing" && <span>Enter: confirm</span>}
          {phase === "reviewing" && <span>Esc: re-record</span>}
        </div>
      </div>
    </div>
  );
}
