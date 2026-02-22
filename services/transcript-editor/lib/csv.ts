import { readFile, writeFile } from "fs/promises";
import { parse } from "csv-parse/sync";
import { stringify } from "csv-stringify/sync";
import path from "path";

export interface ClipRow {
  file_name: string;
  source_file: string;
  start_sec: string;
  end_sec: string;
  duration_sec: string;
  speech_score: string;
  music_score: string;
  transcription: string;
  whisper_avg_logprob: string;
  whisper_no_speech_prob: string;
  whisper_rejected: string;
  corrected: string;
  status: string;
}

export interface ClipData {
  id: number;
  file_name: string;
  duration_sec: number;
  transcription: string;
  speech_score: number;
  music_score: number;
  corrected: boolean;
  status: "pending" | "corrected" | "discarded";
}

function resolveDir(dir: string): string {
  if (path.isAbsolute(dir)) return dir;
  // Resolve relative to project root (2 levels up from services/transcript-editor)
  return path.resolve(process.cwd(), "../..", dir);
}

export async function readClips(dir: string): Promise<ClipData[]> {
  const csvPath = path.join(resolveDir(dir), "metadata.csv");
  const content = await readFile(csvPath, "utf-8");
  const rows: ClipRow[] = parse(content, { columns: true, skip_empty_lines: true });

  return rows.map((row, i) => ({
    id: i,
    file_name: row.file_name,
    duration_sec: parseFloat(row.duration_sec) || 0,
    transcription: row.transcription || "",
    speech_score: parseFloat(row.speech_score) || 0,
    music_score: parseFloat(row.music_score) || 0,
    corrected: row.corrected === "true",
    status: (row.status as ClipData["status"]) || "pending",
  }));
}

export async function updateClip(
  dir: string,
  clipId: number,
  transcription: string,
  status: "corrected" | "discarded"
): Promise<void> {
  const csvPath = path.join(resolveDir(dir), "metadata.csv");
  const content = await readFile(csvPath, "utf-8");
  const rows: ClipRow[] = parse(content, { columns: true, skip_empty_lines: true });

  if (clipId < 0 || clipId >= rows.length) {
    throw new Error(`Clip ID ${clipId} out of range`);
  }

  rows[clipId].transcription = transcription;
  rows[clipId].corrected = "true";
  rows[clipId].status = status;

  const columns = Object.keys(rows[0]);
  // Add new columns if they don't exist
  if (!columns.includes("corrected")) columns.push("corrected");
  if (!columns.includes("status")) columns.push("status");

  const output = stringify(rows, { header: true, columns });
  await writeFile(csvPath, output);
}

export function getAudioPath(dir: string, fileName: string): string {
  return path.join(resolveDir(dir), fileName);
}
