import { encodeWav } from "@/lib/wav";

export interface SilenceRegion {
  readonly start: number;
  readonly end: number;
  readonly midpoint: number;
  readonly duration: number;
}

interface DetectSilencesOptions {
  readonly windowMs?: number;
  readonly minDurationMs?: number;
  readonly rmsThreshold?: number;
}

/**
 * Detect silence regions in an AudioBuffer.
 * Returns regions sorted by duration descending (longest silence first).
 */
export function detectSilences(
  audioBuffer: AudioBuffer,
  options: DetectSilencesOptions = {},
): SilenceRegion[] {
  const {
    windowMs = 100,
    minDurationMs = 300,
    rmsThreshold = 0.01,
  } = options;

  const sampleRate = audioBuffer.sampleRate;
  const channelData = audioBuffer.getChannelData(0);
  const windowSamples = Math.round((windowMs / 1000) * sampleRate);
  const minSilenceSamples = Math.round((minDurationMs / 1000) * sampleRate);

  const regions: SilenceRegion[] = [];
  let silenceStart: number | null = null;

  for (let i = 0; i < channelData.length; i += windowSamples) {
    const end = Math.min(i + windowSamples, channelData.length);
    let sumSquares = 0;
    for (let j = i; j < end; j++) {
      sumSquares += channelData[j] * channelData[j];
    }
    const rms = Math.sqrt(sumSquares / (end - i));

    if (rms < rmsThreshold) {
      if (silenceStart === null) {
        silenceStart = i;
      }
    } else {
      if (silenceStart !== null) {
        const durationSamples = i - silenceStart;
        if (durationSamples >= minSilenceSamples) {
          const start = silenceStart / sampleRate;
          const endSec = i / sampleRate;
          regions.push({
            start,
            end: endSec,
            midpoint: (start + endSec) / 2,
            duration: endSec - start,
          });
        }
        silenceStart = null;
      }
    }
  }

  if (silenceStart !== null) {
    const durationSamples = channelData.length - silenceStart;
    if (durationSamples >= minSilenceSamples) {
      const start = silenceStart / sampleRate;
      const endSec = channelData.length / sampleRate;
      regions.push({
        start,
        end: endSec,
        midpoint: (start + endSec) / 2,
        duration: endSec - start,
      });
    }
  }

  return regions.sort((a, b) => b.duration - a.duration);
}

/**
 * Split a WAV blob at the given boundary timestamps (in seconds).
 * Returns N+1 blobs for N boundaries (sorted ascending).
 */
export async function splitWavAtBoundaries(
  wavBlob: Blob,
  boundaries: readonly number[],
): Promise<Blob[]> {
  const arrayBuffer = await wavBlob.arrayBuffer();
  const audioContext = new AudioContext();

  let decoded: AudioBuffer;
  try {
    decoded = await audioContext.decodeAudioData(arrayBuffer);
  } catch {
    throw new Error("Failed to decode audio data. The file may be corrupted or in an unsupported format.");
  }

  try {
    const sampleRate = decoded.sampleRate;
    const channelData = decoded.getChannelData(0);

    const sorted = [...boundaries].sort((a, b) => a - b);
    const cutPoints = [0, ...sorted, decoded.duration];

    const blobs: Blob[] = [];

    for (let i = 0; i < cutPoints.length - 1; i++) {
      const startSample = Math.round(cutPoints[i] * sampleRate);
      const endSample = Math.round(cutPoints[i + 1] * sampleRate);
      const segment = channelData.slice(startSample, endSample);

      const segmentBuffer = audioContext.createBuffer(1, segment.length, sampleRate);
      segmentBuffer.getChannelData(0).set(segment);

      const wavArrayBuffer = encodeWav(segmentBuffer);
      blobs.push(new Blob([wavArrayBuffer], { type: "audio/wav" }));
    }

    return blobs;
  } finally {
    await audioContext.close();
  }
}
