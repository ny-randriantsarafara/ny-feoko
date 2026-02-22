import { NextRequest, NextResponse } from "next/server";
import { updateClip } from "@/lib/csv";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const dir = request.nextUrl.searchParams.get("dir");
  if (!dir) {
    return NextResponse.json({ error: "Missing dir parameter" }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { transcription, status } = body;

    await updateClip(dir, parseInt(id, 10), transcription, status || "corrected");
    return NextResponse.json({ ok: true });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Failed to update clip";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
