/**
 * Format seconds into m:ss.s format (e.g. "1:23.4").
 */
export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

/**
 * Parse time input: "m:ss.s" or plain seconds.
 * Returns seconds or null if invalid.
 */
export function parseTime(input: string): number | null {
  const trimmed = input.trim();

  const colonMatch = trimmed.match(/^(\d+):(\d+(?:\.\d+)?)$/);
  if (colonMatch) {
    const minutes = parseInt(colonMatch[1], 10);
    const secs = parseFloat(colonMatch[2]);
    if (!isNaN(minutes) && !isNaN(secs) && secs < 60) {
      return minutes * 60 + secs;
    }
    return null;
  }

  const plain = parseFloat(trimmed);
  if (!isNaN(plain) && plain >= 0) {
    return plain;
  }

  return null;
}

/**
 * Format seconds into human-readable duration.
 * Returns "mm:ss" for < 1 hour, "h:mm:ss" for >= 1 hour.
 */
export function formatDuration(totalSeconds: number): string {
  const rounded = Math.round(Math.max(0, totalSeconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const seconds = rounded % 60;

  const mm = String(minutes).padStart(2, "0");
  const ss = String(seconds).padStart(2, "0");

  return hours > 0 ? `${hours}:${mm}:${ss}` : `${minutes}:${ss}`;
}
