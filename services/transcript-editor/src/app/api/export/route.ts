import { proxyToWorker } from "@/lib/worker-proxy";

export async function POST(request: Request) {
  const body = await request.json();
  return proxyToWorker("/export", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
