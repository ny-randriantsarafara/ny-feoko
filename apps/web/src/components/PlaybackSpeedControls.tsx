"use client";

export const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;

export interface PlaybackSpeedControlsProps {
  readonly speed: number;
  readonly onSpeedChange: (speed: number) => void;
}

export function PlaybackSpeedControls({ speed, onSpeedChange }: PlaybackSpeedControlsProps) {
  return (
    <div className="flex items-center gap-1 text-xs text-gray-400">
      {SPEED_OPTIONS.map((s) => (
        <button
          key={s}
          onClick={() => onSpeedChange(s)}
          className={`px-1.5 py-0.5 rounded text-xs ${
            speed === s ? "bg-blue-700 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          {s}x
        </button>
      ))}
    </div>
  );
}
