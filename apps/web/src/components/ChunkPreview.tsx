"use client";

import { estimateChunkDuration } from "@/lib/chunking";

export type ChunkStatus = "pending" | "recording" | "done";

interface ChunkPreviewProps {
  readonly chunks: readonly string[];
  readonly statuses: readonly ChunkStatus[];
  readonly currentIndex: number;
  readonly onSelect: (index: number) => void;
}

export default function ChunkPreview({
  chunks,
  statuses,
  currentIndex,
  onSelect,
}: ChunkPreviewProps) {
  const doneCount = statuses.filter((s) => s === "done").length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700 text-sm text-gray-400">
        <span className="text-green-400 font-medium">{doneCount}</span>/{chunks.length} chunks recorded
      </div>
      <div className="flex-1 overflow-y-auto">
        {chunks.map((chunk, index) => {
          const status = statuses[index];
          const isCurrent = index === currentIndex;
          const estimatedSec = estimateChunkDuration(chunk);

          return (
            <button
              key={index}
              onClick={() => onSelect(index)}
              className={`w-full text-left px-4 py-3 border-b border-gray-800 transition-colors ${
                isCurrent
                  ? "bg-[#1a1a3a] border-l-2 border-l-blue-500"
                  : "hover:bg-[#161622] border-l-2 border-l-transparent"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono text-gray-500">
                  #{index + 1}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">~{estimatedSec}s</span>
                  <span
                    className={`w-2 h-2 rounded-full ${
                      status === "done"
                        ? "bg-green-500"
                        : status === "recording"
                          ? "bg-red-500 animate-pulse"
                          : "bg-gray-600"
                    }`}
                  />
                </div>
              </div>
              <p className="text-sm text-gray-300 line-clamp-2 leading-relaxed">
                {chunk}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
