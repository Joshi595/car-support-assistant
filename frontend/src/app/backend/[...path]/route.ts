import type { NextRequest } from "next/server";

// The customer API on the web app's own origin: the browser calls /backend/v1/..., this server forwards to
// the API. One public origin means one tunnel or domain is enough, and no CORS. Agent routes are not
// forwarded here; they go through /api/agent, which checks the agent's sign-in.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
const ALLOWED = new Set(["chat", "feedback", "handoff", "conversations"]);

async function forward(request: NextRequest, ctx: RouteContext<"/backend/[...path]">): Promise<Response> {
  const { path } = await ctx.params;
  if (path[0] !== "v1" || !ALLOWED.has(path[1] ?? "")) {
    return Response.json({ detail: "not found" }, { status: 404 });
  }
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // The API rate-limits per customer, so it needs the customer's address, not this server's.
  const client = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (client) headers["X-Forwarded-For"] = client;
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers["X-Request-ID"] = requestId;

  const response = await fetch(`${API_URL}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: request.method === "GET" ? undefined : await request.text(),
    cache: "no-store",
  });
  // Stream the body through unchanged: chat answers arrive as Server-Sent Events.
  return new Response(response.body, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json",
      "Cache-Control": "no-cache",
      "X-Request-ID": response.headers.get("X-Request-ID") ?? "",
    },
  });
}

export const GET = forward;
export const POST = forward;
