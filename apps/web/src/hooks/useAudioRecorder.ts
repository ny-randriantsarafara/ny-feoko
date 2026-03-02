import { useRef, useState, useCallback } from "react";
import { blobToWav } from "@/lib/wav";

interface AudioRecorderState {
  readonly isRecording: boolean;
  readonly wavBlob: Blob | null;
  readonly durationSec: number;
  readonly error: string | null;
}

interface AudioRecorderActions {
  readonly startRecording: () => Promise<void>;
  readonly stopRecording: () => void;
  readonly reset: () => void;
}

export type AudioRecorder = AudioRecorderState & AudioRecorderActions;

export function useAudioRecorder(): AudioRecorder {
  const [isRecording, setIsRecording] = useState(false);
  const [wavBlob, setWavBlob] = useState<Blob | null>(null);
  const [durationSec, setDurationSec] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startTimeRef = useRef<number>(0);

  const stopMediaStream = useCallback(() => {
    const stream = streamRef.current;
    if (!stream) return;
    for (const track of stream.getTracks()) {
      track.stop();
    }
    streamRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    setWavBlob(null);
    setDurationSec(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stopMediaStream();
        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        setDurationSec(elapsed);

        const rawBlob = new Blob(chunks, { type: recorder.mimeType });
        try {
          const wav = await blobToWav(rawBlob);
          setWavBlob(wav);
        } catch {
          setError("Failed to encode audio to WAV");
        }
      };

      startTimeRef.current = Date.now();
      recorder.start();
      setIsRecording(true);
    } catch {
      setError("Microphone access denied");
    }
  }, [stopMediaStream]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === "recording") {
      recorder.stop();
    }
    setIsRecording(false);
  }, []);

  const reset = useCallback(() => {
    setWavBlob(null);
    setDurationSec(0);
    setError(null);
  }, []);

  return {
    isRecording,
    wavBlob,
    durationSec,
    error,
    startRecording,
    stopRecording,
    reset,
  };
}
