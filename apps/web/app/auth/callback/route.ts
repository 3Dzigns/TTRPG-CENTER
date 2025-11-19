import { NextRequest, NextResponse } from "next/server";
import { upsertOAuthUser, createSession } from "@/lib/auth/repository";
import {
  encodeSessionCookie,
  generateSessionSecret,
  getSessionExpiryDate,
  sessionCookieName
} from "@/lib/auth/session";

const AUTH_BASE_URL = process.env.AUTH_BASE_URL ?? process.env.API_BASE_URL ?? "";
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET;
const GOOGLE_REDIRECT_URI = process.env.GOOGLE_REDIRECT_URI;
const OAUTH_STATE_COOKIE = "oauth_state";
const resolveAppOrigin = (request: NextRequest): string => {
  if (process.env.PUBLIC_APP_URL) {
    return process.env.PUBLIC_APP_URL.replace(/\/$/, "");
  }
  const proto =
    request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(/:$/, "") ?? "http";
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? "localhost:3000";
  return `${proto}://${host}`.replace(/\/$/, "");
};

const normalizeRedirectTarget = (target: string | undefined, base: string): URL => {
  if (!target) {
    return new URL("/", base);
  }
  if (target.startsWith("/")) {
    return new URL(target, base);
  }
  try {
    const parsed = new URL(target);
    if (parsed.origin === base) {
      return parsed;
    }
  } catch {
    // ignore invalid target
  }
  return new URL("/", base);
};

const TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token";
const TOKEN_INFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo";

function parseStatePayload(stateParam: string | null): { nonce: string; redirect?: string } | null {
  if (!stateParam) {
    return null;
  }
  try {
    const decoded = Buffer.from(stateParam, "base64url").toString("utf8");
    const payload = JSON.parse(decoded) as { nonce: string; redirect?: string };
    if (typeof payload?.nonce === "string") {
      return payload;
    }
  } catch {
    // ignore
  }
  return null;
}

function buildErrorRedirect(request: NextRequest, reason: string) {
  const url = new URL("/auth/signin", request.url);
  url.searchParams.set("error", reason);
  const response = NextResponse.redirect(url);
  response.cookies.delete(sessionCookieName);
  response.cookies.delete(OAUTH_STATE_COOKIE);
  return response;
}

function normaliseRedirect(origin: string, target: string | undefined) {
  try {
    return normalizeRedirectTarget(target, origin);
  } catch {
    return new URL("/", origin);
  }
}

export async function GET(request: NextRequest) {
  if (AUTH_BASE_URL) {
    const callbackUrl = new URL("/auth/callback", AUTH_BASE_URL);
    request.nextUrl.searchParams.forEach((value, key) => {
      callbackUrl.searchParams.set(key, value);
    });

    const response = await fetch(callbackUrl.toString(), {
      method: "GET",
      headers: {
        cookie: request.headers.get("cookie") ?? ""
      },
      redirect: "manual"
    });

    const redirectPath = request.nextUrl.searchParams.get("redirect") ?? "/";
    const nextResponse = NextResponse.redirect(new URL(redirectPath, request.url));
    const setCookieHeader = response.headers.get("set-cookie");

    if (setCookieHeader) {
      setCookieHeader.split(/, (?=[^\s]+=)/).forEach((cookie) => {
        nextResponse.headers.append("set-cookie", cookie);
      });
    } else {
      nextResponse.cookies.delete(sessionCookieName);
    }

    return nextResponse;
  }

  if (!GOOGLE_CLIENT_ID || !GOOGLE_CLIENT_SECRET) {
    const statePayload = parseStatePayload(request.nextUrl.searchParams.get("state"));
    const redirectUrl = statePayload?.redirect ?? request.nextUrl.searchParams.get("redirect") ?? "/";
    const response = NextResponse.redirect(new URL(redirectUrl, request.url));
    response.cookies.delete(sessionCookieName);
    response.cookies.delete(OAUTH_STATE_COOKIE);
    return response;
  }

  const searchParams = request.nextUrl.searchParams;

  if (searchParams.get("error")) {
    return buildErrorRedirect(request, searchParams.get("error") ?? "access_denied");
  }

  const code = searchParams.get("code");
  const stateParam = searchParams.get("state");
  const stateCookie = request.cookies.get(OAUTH_STATE_COOKIE)?.value;

  if (!code || !stateParam || !stateCookie || stateParam !== stateCookie) {
    return buildErrorRedirect(request, "invalid_state");
  }

  const statePayload = parseStatePayload(stateParam);
  if (!statePayload) {
    return buildErrorRedirect(request, "invalid_state");
  }

  const appOrigin = resolveAppOrigin(request);
  const callbackUrl = GOOGLE_REDIRECT_URI ?? `${appOrigin}/auth/callback`;
  const tokenRequestBody = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    client_secret: GOOGLE_CLIENT_SECRET,
    code,
    grant_type: "authorization_code",
    redirect_uri: callbackUrl
  });

  const tokenResponse = await fetch(TOKEN_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: tokenRequestBody.toString()
  });

  if (!tokenResponse.ok) {
    return buildErrorRedirect(request, "token_exchange_failed");
  }

  const tokenPayload = (await tokenResponse.json().catch(() => null)) as
    | {
        access_token?: string;
        expires_in?: number;
        id_token?: string;
        refresh_token?: string;
        token_type?: string;
      }
    | null;

  if (!tokenPayload?.id_token) {
    return buildErrorRedirect(request, "token_missing");
  }

  const tokenInfoResponse = await fetch(`${TOKEN_INFO_ENDPOINT}?id_token=${tokenPayload.id_token}`);

  if (!tokenInfoResponse.ok) {
    return buildErrorRedirect(request, "token_invalid");
  }

  const tokenInfo = (await tokenInfoResponse.json().catch(() => null)) as
    | {
        aud?: string;
        email?: string;
        name?: string;
        picture?: string;
        sub?: string;
        exp?: string;
      }
    | null;

  if (!tokenInfo || tokenInfo.aud !== GOOGLE_CLIENT_ID) {
    return buildErrorRedirect(request, "token_invalid");
  }

  if (!tokenInfo.email || !tokenInfo.name || !tokenInfo.sub) {
    return buildErrorRedirect(request, "token_missing_profile");
  }

  const expiresAt = getSessionExpiryDate();

  let upsertedUser;
  try {
    const { user } = await upsertOAuthUser({
      email: tokenInfo.email,
      displayName: tokenInfo.name,
      avatarUrl: tokenInfo.picture,
      provider: "google",
      providerAccountId: tokenInfo.sub,
      accessToken: tokenPayload.access_token ?? null,
      refreshToken: tokenPayload.refresh_token ?? null,
      expiresAt: tokenPayload.expires_in
        ? new Date(Date.now() + Number(tokenPayload.expires_in) * 1000)
        : null,
      rawProfile: tokenInfo as Record<string, unknown>
    });
    upsertedUser = user;
  } catch (error) {
    console.error("Failed to store OAuth user", error);
    return buildErrorRedirect(request, "storage_unavailable");
  }

  const secret = generateSessionSecret();
  let sessionId: string;
  try {
    sessionId = await createSession({
      userId: upsertedUser.id,
      secret,
      expiresAt,
      userAgent: request.headers.get("user-agent"),
      ipAddress: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
    });
  } catch (error) {
    console.error("Failed to create session", error);
    return buildErrorRedirect(request, "storage_unavailable");
  }

  const redirectUrl = normaliseRedirect(appOrigin, statePayload.redirect);
  const sessionValue = encodeSessionCookie(sessionId, secret);

  const response = NextResponse.redirect(redirectUrl);
  response.cookies.set({
    name: sessionCookieName,
    value: sessionValue,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    expires: expiresAt,
    path: "/"
  });
  response.cookies.delete(OAUTH_STATE_COOKIE);

  return response;
}
