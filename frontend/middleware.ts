import { NextRequest, NextResponse } from "next/server";

const PROTECTED_PATHS = ["/add"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only protect write-access routes
  if (!PROTECTED_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const token = request.cookies.get("access_token")?.value;

  if (!token) {
    // Redirect to login with return URL
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("returnTo", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Inject token into backend API proxy requests
  const response = NextResponse.next();
  return response;
}

export const config = {
  matcher: ["/add/:path*"],
};
