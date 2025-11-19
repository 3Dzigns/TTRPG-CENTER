import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const AUTH_BASE_URL = process.env.AUTH_BASE_URL ?? process.env.API_BASE_URL ?? "";
const AUTH_COOKIE_NAME = process.env.AUTH_COOKIE_NAME ?? "tc_session";
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const GOOGLE_REDIRECT_URI = process.env.GOOGLE_REDIRECT_URI;
const OAUTH_STATE_COOKIE = "oauth_state";

const resolveAppOrigin = (request: NextRequest): string => {
  if (process.env.PUBLIC_APP_URL) {
    return process.env.PUBLIC_APP_URL.replace(/\/$/, "");
  }
  const proto =
    request.headers.get("x-forwarded-proto") ??
    request.nextUrl.protocol.replace(/:$/, "") ??
    "http";
  const host =
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    "localhost:3000";
  return `${proto}://${host}`.replace(/\/$/, "");
};

const normaliseRedirectTarget = (redirect: string | undefined): string => {
  if (!redirect) {
    return "/";
  }
  if (redirect.startsWith("/")) {
    return redirect;
  }
  try {
    const url = new URL(redirect);
    return url.pathname + url.search + url.hash;
  } catch {
    return "/";
  }
};

export async function POST(request: NextRequest) {
  const { provider, redirect } = (await request.json().catch(() => ({}))) as {
    provider?: string;
    redirect?: string;
  };

  if (!provider) {
    return NextResponse.json({ error: "Missing provider" }, { status: 400 });
  }

  if (AUTH_BASE_URL) {
    const backendResponse = await fetch(`${AUTH_BASE_URL}/auth/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        cookie: request.headers.get("cookie") ?? ""
      },
      body: JSON.stringify({ provider, redirect }) as BodyInit,
      redirect: "manual"
    });

    const cookies = backendResponse.headers.get("set-cookie");

    if (backendResponse.status >= 300 && backendResponse.status < 400) {
      const location = backendResponse.headers.get("location");
      if (location) {
        const response = NextResponse.json({ redirectTo: location });
        if (cookies) {
          cookies.split(/, (?=[^\s]+=)/).forEach((cookie) => response.headers.append("set-cookie", cookie));
        }
        return response;
      }
    }

    let redirectTo: string | undefined;
    try {
      const data = await backendResponse.json();
      redirectTo = data.redirectTo ?? data.url;
    } catch {
      redirectTo = undefined;
    }

    const fallback = `${AUTH_BASE_URL}/auth/start?provider=${provider}`;
    const response = NextResponse.json({ redirectTo: redirectTo ?? fallback });

    if (cookies) {
      cookies.split(/, (?=[^\s]+=)/).forEach((cookie) => response.headers.append("set-cookie", cookie));
    } else {
      response.cookies.delete(AUTH_COOKIE_NAME);
    }

    return response;
  }

  const normalizedProvider = provider === "oidc" ? "google" : provider;

  if (normalizedProvider !== "google") {
    return NextResponse.json({ error: "Unsupported provider" }, { status: 400 });
  }

  if (!GOOGLE_CLIENT_ID) {
    const redirectTarget = normaliseRedirectTarget(redirect);
    return NextResponse.json({ redirectTo: redirectTarget });
  }

  const appOrigin = resolveAppOrigin(request);
  const redirectTarget = normaliseRedirectTarget(redirect);
  const stateNonce = randomBytes(24).toString("hex");
  const statePayload = { nonce: stateNonce, redirect: redirectTarget };
  const encodedState = Buffer.from(JSON.stringify(statePayload)).toString("base64url");

  const callbackUrl = GOOGLE_REDIRECT_URI ?? `${appOrigin}/auth/callback`;

  const searchParams = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: callbackUrl,
    response_type: "code",
    scope: "openid email profile",
    state: encodedState,
    access_type: "offline",
    prompt: "consent"
  });

  const response = NextResponse.json({
    redirectTo: `https://accounts.google.com/o/oauth2/v2/auth?${searchParams.toString()}`
  });

  response.cookies.set({
    name: OAUTH_STATE_COOKIE,
    value: encodedState,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 5,
    path: "/"
  });

  return response;
}
