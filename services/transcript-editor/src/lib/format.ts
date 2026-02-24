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
