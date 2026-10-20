import { SignJWT } from "jose";
import type { NextRequest } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions, isAgent } from "@/lib/auth";

// Agent requests go through the frontend's server: it checks the agent's session, then calls the backend's
// /v1/admin routes with a short-lived token signed with the shared secret. The browser never sees the secret.
const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function forward(request: NextRequest, ctx: RouteContext<"/api/agent/[...path]">): Promise<Response> {
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!isAgent(email)) {
    return Response.json({ detail: "sign in as an agent" }, { status: 401 });
  }
  const secret = process.env.AGENT_JWT_SECRET;
  if (!secret) {
    return Response.json({ detail: "AGENT_JWT_SECRET is not configured" }, { status: 503 });
  }
  const token = await new SignJWT({ role: "agent" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(email!)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(new TextEncoder().encode(secret));

  const { path } = await ctx.params;
  const target = `${API_URL}/v1/admin/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const response = await fetch(target, {
    method: request.method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: request.method === "GET" ? undefined : await request.text(),
    cache: "no-store",
  });
  return new Response(response.body, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
