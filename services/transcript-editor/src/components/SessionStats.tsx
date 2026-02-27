"use client";

import { useState, useEffect } from "react";

interface SessionStatsProps {
  sessionDoneCount: number;
  sessionStartMs: number;
  pendingCount: number;
}

export default function SessionStats({ sessionDoneCount, sessionStartMs, pendingCount }: SessionStatsProps) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(interval);
  }, []);

  if (sessionDoneCount === 0) return null;

  const elapsedMin = Math.max(0.5, (now - sessionStartMs) / 60_000);
  const pace = sessionDoneCount / elapsedMin;
  const etaMin = pendingCount > 0 ? Math.ceil(pendingCount / pace) : 0;

  return (
    <div className="flex items-center gap-4 px-4 md:px-6 py-1.5 bg-[#0d0d1a] border-b border-gray-800 text-xs text-gray-400">
      <span>
        <span className="text-green-400 font-medium">{sessionDoneCount}</span> done this session
      </span>
      <span>~{pace.toFixed(1)} clips/min</span>
      {pendingCount > 0 && (
        <span>~{etaMin} min remaining ({pendingCount} pending)</span>
      )}
    </div>
  );
}
