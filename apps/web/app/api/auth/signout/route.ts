import { NextRequest, NextResponse } from "next/server";
import { decodeSessionCookie, sessionCookieName } from "@/lib/auth/session";
import { revokeSession } from "@/lib/auth/repository";

const AUTH_BASE_URL = process.env.AUTH_BASE_URL ?? process.env.API_BASE_URL ?? "";
const OAUTH_STATE_COOKIE = "oauth_state";

export async function POST(request: NextRequest) {
  if (!AUTH_BASE_URL) {
    const sessionValue = request.cookies.get(sessionCookieName)?.value;
    const decoded = decodeSessionCookie(sessionValue);
    if (decoded) {
      await revokeSession(decoded.sessionId, decoded.secret);
    }

    const response = NextResponse.json({ ok: true });
    response.cookies.delete(sessionCookieName);
    response.cookies.delete(OAUTH_STATE_COOKIE);
    return response;
  }

  const backendResponse = await fetch(`${AUTH_BASE_URL}/auth/signout`, {
    method: "POST",
    headers: {
      cookie: request.headers.get("cookie") ?? ""
    },
    redirect: "manual"
  });

  const response = NextResponse.json({ ok: true });
  const cookies = backendResponse.headers.get("set-cookie");

  if (cookies) {
    cookies.split(/, (?=[^\s]+=)/).forEach((cookie) => response.headers.append("set-cookie", cookie));
  } else {
    response.cookies.delete(sessionCookieName);
  }

  response.cookies.delete(OAUTH_STATE_COOKIE);

  return response;
}
