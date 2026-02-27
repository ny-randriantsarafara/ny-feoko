"use client";

import {
  useRef,
  useEffect,
  useImperativeHandle,
  forwardRef,
  useCallback,
} from "react";
import WaveSurfer from "wavesurfer.js";

export interface WaveformHandle {
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  replay: () => void;
  jumpBack: (seconds: number) => void;
  setSpeed: (rate: number) => void;
}

interface WaveformProps {
  audioUrl: string;
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onFinish: () => void;
  onReady?: () => void;
}

const Waveform = forwardRef<WaveformHandle, WaveformProps>(function Waveform(
  { audioUrl, speed, onPlay, onPause, onFinish, onReady },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#4a4a6a",
      progressColor: "#6366f1",
      cursorColor: "#818cf8",
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 64,
      normalize: true,
    });

    ws.on("play", onPlay);
    ws.on("pause", onPause);
    ws.on("finish", onFinish);
    if (onReady) {
      ws.on("ready", onReady);
    }

    ws.load(audioUrl);
    wsRef.current = ws;

    return () => {
      ws.destroy();
      wsRef.current = null;
    };
    // Only recreate when audioUrl changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl]);

  useEffect(() => {
    if (wsRef.current) {
      wsRef.current.setPlaybackRate(speed, true);
    }
  }, [speed]);

  const play = useCallback(() => {
    wsRef.current?.play();
  }, []);

  const pause = useCallback(() => {
    wsRef.current?.pause();
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

  const jumpBack = useCallback((seconds: number) => {
    const ws = wsRef.current;
    if (!ws) return;
    const duration = ws.getDuration();
    if (duration === 0) return;
    const newTime = Math.max(0, ws.getCurrentTime() - seconds);
    ws.seekTo(newTime / duration);
    ws.play();
  }, []);

  const setSpeed = useCallback((rate: number) => {
    wsRef.current?.setPlaybackRate(rate, true);
  }, []);

  useImperativeHandle(ref, () => ({
    play,
    pause,
    togglePlay,
    replay,
    jumpBack,
    setSpeed,
  }));

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg bg-[#1a1a2e] border border-[#2a2a4a] p-2 cursor-pointer"
    />
  );
});

export default Waveform;
