import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME ?? "tc_session";
const PROTECTED_PATHS = ["/player", "/gm", "/admin", "/game"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PATHS.some((path) => pathname.startsWith(path));

  if (isProtected) {
    const hasSession = request.cookies.get(AUTH_COOKIE_NAME) ?? request.cookies.get("session");
    if (!hasSession) {
      const redirect = new URL("/auth/signin", request.url);
      redirect.searchParams.set("redirect", pathname + request.nextUrl.search);
      return NextResponse.redirect(redirect);
    }
  }

  if (pathname === "/auth/signin") {
    const hasSession = request.cookies.get(AUTH_COOKIE_NAME) ?? request.cookies.get("session");
    if (hasSession) {
      const redirectTarget = request.nextUrl.searchParams.get("redirect") ?? "/player";
      return NextResponse.redirect(new URL(redirectTarget, request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/(player|gm|admin|game|auth/signin)"]
};
