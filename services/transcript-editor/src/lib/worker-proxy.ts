const WORKER_URL = process.env.WORKER_URL ?? "http://localhost:8000";

export async function proxyToWorker(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const url = `${WORKER_URL}${path}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    return new Response(response.body, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json(
      { error: "API worker is not reachable. Start it with: ./ambara api" },
      { status: 502 },
    );
  }
}
