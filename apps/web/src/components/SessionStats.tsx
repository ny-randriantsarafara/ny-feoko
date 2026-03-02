"use client";

import { useState, useEffect, useRef } from "react";

interface SessionStatsProps {
  readonly sessionDoneCount: number;
  readonly sessionStartMs: number;
  readonly pendingCount: number;
}

const MILESTONES = [10, 25, 50, 100, 200, 500] as const;

export default function SessionStats({ sessionDoneCount, sessionStartMs, pendingCount }: SessionStatsProps) {
  const [now, setNow] = useState(Date.now());
  const [celebrating, setCelebrating] = useState(false);
  const prevCountRef = useRef(sessionDoneCount);

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const prev = prevCountRef.current;
    prevCountRef.current = sessionDoneCount;

    if (sessionDoneCount > prev && MILESTONES.includes(sessionDoneCount as typeof MILESTONES[number])) {
      setCelebrating(true);
      const timer = setTimeout(() => setCelebrating(false), 1500);
      return () => clearTimeout(timer);
    }
  }, [sessionDoneCount]);

  if (sessionDoneCount === 0) return null;

  const elapsedMin = Math.max(0.5, (now - sessionStartMs) / 60_000);
  const pace = sessionDoneCount / elapsedMin;
  const etaMin = pendingCount > 0 ? Math.ceil(pendingCount / pace) : 0;

  return (
    <div
      className={`flex items-center gap-4 px-4 md:px-6 py-1.5 bg-[#0d0d1a] border-b border-gray-800 text-xs text-gray-400 transition-all duration-500 ${
        celebrating ? "scale-[1.03] bg-green-950/30 border-green-800/50" : ""
      }`}
    >
      <span>
        <span className={`font-medium transition-colors duration-500 ${celebrating ? "text-yellow-300" : "text-green-400"}`}>
          {sessionDoneCount}
        </span>
        {" "}done this session
      </span>
      <span>~{pace.toFixed(1)} clips/min</span>
      {pendingCount > 0 && (
        <span>~{etaMin} min remaining ({pendingCount} pending)</span>
      )}
    </div>
  );
}
