import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";

export async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const backendPath = path.join("/");
  const url = new URL(`/api/${backendPath}`, BACKEND_URL);
  url.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  // Prefer cookie-based auth (Keycloak OIDC), fall back to env API_TOKEN
  const cookieToken = request.cookies.get("access_token")?.value;
  const token = cookieToken || process.env.API_TOKEN;
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.delete("host");

  const body =
    request.method !== "GET" && request.method !== "HEAD"
      ? await request.arrayBuffer()
      : undefined;

  const response = await fetch(url.toString(), {
    method: request.method,
    headers,
    body,
  });

  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
