import { NextRequest, NextResponse } from "next/server";
import { readClips } from "@/lib/csv";

export async function GET(request: NextRequest) {
  const dir = request.nextUrl.searchParams.get("dir");
  if (!dir) {
    return NextResponse.json({ error: "Missing dir parameter" }, { status: 400 });
  }

  try {
    const clips = await readClips(dir);
    return NextResponse.json(clips);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to read clips";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
