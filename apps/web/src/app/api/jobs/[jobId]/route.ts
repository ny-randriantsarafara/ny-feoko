import { proxyToWorker } from "@/lib/worker-proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  return proxyToWorker(`/jobs/${jobId}`);
}
