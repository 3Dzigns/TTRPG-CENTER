import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "../middleware";

const buildRequest = (url: string, cookie?: string) =>
  new NextRequest(url, {
    headers: cookie
      ? {
          cookie
        }
      : undefined
  });

describe("middleware", () => {
  it("redirects unauthenticated requests on protected routes", () => {
    const request = buildRequest("http://localhost/player");
    const response = middleware(request);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/auth/signin?redirect=%2Fplayer");
  });

  it("allows authenticated requests to proceed on protected routes", () => {
    const request = buildRequest("http://localhost/gm", "tc_session=session-token");
    const response = middleware(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects authenticated users away from the sign-in page", () => {
    const request = buildRequest("http://localhost/auth/signin?redirect=%2Fgm", "tc_session=session-token");
    const response = middleware(request);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost/gm");
  });
});
