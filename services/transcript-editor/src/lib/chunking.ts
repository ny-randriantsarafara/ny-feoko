const MALAGASY_WPM = 130;
const MIN_CHUNK_SECONDS = 5;
const MAX_CHUNK_SECONDS = 25;

function estimateReadingSeconds(text: string): number {
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  return (wordCount / MALAGASY_WPM) * 60;
}

function splitIntoSentences(text: string): string[] {
  const raw = text.split(/(?<=[.!?।])\s+/);
  return raw.map((s) => s.trim()).filter(Boolean);
}

export function splitPassageIntoChunks(text: string): string[] {
  const sentences = splitIntoSentences(text);

  if (sentences.length === 0) {
    return [];
  }

  const chunks: string[] = [];
  let current: string[] = [];
  let currentSeconds = 0;

  for (const sentence of sentences) {
    const sentenceSeconds = estimateReadingSeconds(sentence);

    if (current.length > 0 && currentSeconds + sentenceSeconds > MAX_CHUNK_SECONDS) {
      chunks.push(current.join(" "));
      current = [sentence];
      currentSeconds = sentenceSeconds;
      continue;
    }

    current.push(sentence);
    currentSeconds += sentenceSeconds;
  }

  if (current.length > 0) {
    const remaining = current.join(" ");

    if (chunks.length > 0 && estimateReadingSeconds(remaining) < MIN_CHUNK_SECONDS) {
      chunks[chunks.length - 1] += " " + remaining;
    } else {
      chunks.push(remaining);
    }
  }

  return chunks;
}

export function estimateChunkDuration(text: string): number {
  return Math.round(estimateReadingSeconds(text));
}
