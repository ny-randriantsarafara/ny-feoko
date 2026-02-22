import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { getAudioPath } from "@/lib/csv";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ file: string }> }
) {
  const { file } = await params;
  const dir = request.nextUrl.searchParams.get("dir");
  if (!dir) {
    return NextResponse.json({ error: "Missing dir parameter" }, { status: 400 });
  }

  try {
    const audioPath = getAudioPath(dir, `clips/${file}`);
    const buffer = await readFile(audioPath);

    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "audio/wav",
        "Content-Length": buffer.byteLength.toString(),
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch {
    return NextResponse.json({ error: "Audio file not found" }, { status: 404 });
  }
}
