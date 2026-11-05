import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.TAXRAG_API_BASE_URL ?? "http://127.0.0.1:8000";

type RouteContext = { params: Promise<{ path: string[] }> };

/** Keep browser requests same-origin and forward only the Eval Workshop API routes. */
async function forward(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const apiPath = `/${path.map(encodeURIComponent).join("/")}`;
  const allowedRoute =
    apiPath === "/api/evals/suites" ||
    apiPath === "/api/evals/artifacts" ||
    apiPath === "/api/evals/debug-answer" ||
    apiPath === "/api/evals/baselines" ||
    apiPath === "/api/evals/compare" ||
    /^\/api\/evals\/suites\/[a-z0-9_-]+\/run$/.test(apiPath) ||
    /^\/api\/evals\/suites\/[a-z0-9_-]+\/jobs$/.test(apiPath) ||
    /^\/api\/evals\/jobs\/[a-f0-9]+$/.test(apiPath) ||
    /^\/api\/evals\/suites\/[a-z0-9_-]+\/fixture$/.test(apiPath) ||
    /^\/api\/evals\/artifacts\/[a-zA-Z0-9_.-]+$/.test(apiPath);

  if (!allowedRoute) {
    return NextResponse.json({ detail: "Unknown local TaxRAG route" }, { status: 404 });
  }

  const target = new URL(`${apiPath}${request.nextUrl.search}`, API_BASE_URL);
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: `Cannot reach the TaxRAG API at ${API_BASE_URL}. Start it with: uv run uvicorn apps.api.main:app --reload` },
      { status: 502 },
    );
  }
}

export const GET = forward;
export const PUT = forward;
export const POST = forward;
