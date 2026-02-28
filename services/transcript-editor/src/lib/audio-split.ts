import { encodeWav } from "@/lib/wav";

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

  try {
    const decoded = await audioContext.decodeAudioData(arrayBuffer);
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
