"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function ReadingSessionRedirect() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/runs/${runId}`);
  }, [runId, router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-gray-500">Redirecting...</p>
    </div>
  );
}
