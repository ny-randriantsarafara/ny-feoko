"use client";

import { useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { splitPassageIntoChunks } from "@/lib/chunking";

export default function ReadingSetupPage() {
  const router = useRouter();

  const [passage, setPassage] = useState("");
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const previewChunks = useMemo(() => {
    if (passage.trim().length === 0) return [];
    return splitPassageIntoChunks(passage);
  }, [passage]);

  const handleStartSession = useCallback(async () => {
    const sessionChunks = splitPassageIntoChunks(passage);
    if (sessionChunks.length === 0) return;

    const sessionLabel = label.trim() || `reading-${new Date().toISOString().slice(0, 10)}`;

    setCreating(true);
    setError(null);

    const supabase = createClient();

    const { data: run, error: runError } = await supabase
      .from("runs")
      .insert({ label: sessionLabel, source: passage.slice(0, 200), type: "reading" })
      .select("id")
      .single();

    if (runError || !run) {
      setError(runError?.message ?? "Failed to create session");
      setCreating(false);
      return;
    }

    const clipRows = sessionChunks.map((text, index) => ({
      run_id: run.id,
      file_name: `chunks/${String(index).padStart(4, "0")}.wav`,
      draft_transcription: text,
      status: "pending" as const,
      priority: sessionChunks.length - index,
    }));

    const { error: clipsError } = await supabase.from("clips").insert(clipRows);

    if (clipsError) {
      setError(clipsError.message);
      setCreating(false);
      return;
    }

    router.push(`/read/${run.id}`);
  }, [passage, label, router]);

  return (
    <div style={{ maxWidth: 700, margin: "0 auto", padding: "40px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>New Reading Session</h1>
        <button
          onClick={() => router.push("/")}
          className="text-blue-500 text-sm hover:underline"
        >
          Cancel
        </button>
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">
            Session label (optional)
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={`reading-${new Date().toISOString().slice(0, 10)}`}
            className="w-full px-3 py-2 text-sm bg-[#1e1e1e] text-gray-200 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">
            Paste your passage
          </label>
          <textarea
            value={passage}
            onChange={(e) => setPassage(e.target.value)}
            placeholder="Paste the Malagasy text you want to read aloud..."
            className="w-full min-h-[200px] p-4 text-base leading-relaxed font-sans bg-[#1e1e1e] text-gray-200 border border-gray-700 rounded-lg resize-y focus:outline-none focus:border-blue-500"
          />
        </div>

        {previewChunks.length > 0 && (
          <div className="p-3 bg-[#1a1a2e] border border-[#2a2a4a] rounded-lg">
            <div className="text-xs text-gray-500 mb-2">
              Will be split into {previewChunks.length} chunk{previewChunks.length > 1 ? "s" : ""}
            </div>
            <div className="flex flex-col gap-2 max-h-[200px] overflow-y-auto">
              {previewChunks.map((chunk, i) => (
                <div key={i} className="text-sm text-gray-400 flex gap-2">
                  <span className="text-gray-600 font-mono shrink-0">#{i + 1}</span>
                  <span className="line-clamp-1">{chunk}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="text-sm text-red-400">{error}</div>
        )}

        <button
          onClick={handleStartSession}
          disabled={previewChunks.length === 0 || creating}
          className="w-full py-3 rounded-lg bg-blue-700 hover:bg-blue-600 text-white font-medium text-base disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {creating ? "Creating..." : `Start Recording (${previewChunks.length} chunks)`}
        </button>
      </div>
    </div>
  );
}
