import { NextRequest, NextResponse } from "next/server";

// Redirects to /login when the session cookie is missing. This is convenience only,
// not security (ARCHITECTURE.md section 7) - the cookie is signed and httpOnly, and
// every real access/role check happens on the FastAPI side. Role-gating of /admin
// pages happens client-side (fetch /api/me, redirect if not Administrator), since
// middleware here cannot verify the cookie's signature without sharing the backend's
// secret key.
const PROTECTED_PREFIXES = ["/dashboard", "/satellites", "/evaluation", "/admin", "/globe"];
const SESSION_COOKIE = "os_session";

export function middleware(request: NextRequest) {
  const isProtected = PROTECTED_PREFIXES.some((prefix) => request.nextUrl.pathname.startsWith(prefix));
  if (isProtected && !request.cookies.has(SESSION_COOKIE)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/satellites/:path*", "/evaluation/:path*", "/admin/:path*", "/globe/:path*", "/globe"],
};
