import { proxyToWorker } from "@/lib/worker-proxy";

export async function GET() {
  return proxyToWorker("/jobs");
}
