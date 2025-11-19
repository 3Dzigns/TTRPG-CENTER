import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, extractTraceId } from "../index";

const createClientWithResponse = (response: Response) => {
  const fetchMock = vi.fn().mockResolvedValue(response);
  return {
    client: new ApiClient({ baseUrl: "", fetchImpl: fetchMock }),
    fetchMock
  };
};

describe("ApiClient error handling", () => {
  it("surfaces envelope message, trace id, and code", async () => {
    const body = {
      error: {
        message: "You cannot perform this action right now.",
        trace_id: "trace-123",
        code: "forbidden"
      }
    };
    const response = new Response(JSON.stringify(body), {
      status: 403,
      headers: { "Content-Type": "application/json" }
    });

    const { client } = createClientWithResponse(response);

    let thrown: unknown;
    await expect(async () => {
      try {
        await client.getGames();
      } catch (error) {
        thrown = error;
        throw error;
      }
    }).rejects.toBeInstanceOf(ApiError);

    const apiError = thrown as ApiError;
    expect(apiError).toBeInstanceOf(ApiError);
    expect(apiError.message).toBe("You cannot perform this action right now.");
    expect(apiError.status).toBe(403);
    expect(apiError.traceId).toBe("trace-123");
    expect(apiError.code).toBe("forbidden");
    expect(apiError.details).toEqual(body);
  });

  it("falls back to friendly messages for generic failures", async () => {
    const response = new Response("upstream failed", {
      status: 500,
      statusText: "",
      headers: { "Content-Type": "text/plain" }
    });

    const { client } = createClientWithResponse(response);

    let thrown: unknown;
    await expect(async () => {
      try {
        await client.getGames();
      } catch (error) {
        thrown = error;
        throw error;
      }
    }).rejects.toBeInstanceOf(ApiError);

    const apiError = thrown as ApiError;
    expect(apiError).toBeInstanceOf(ApiError);
    expect(apiError.message).toBe("Something went wrong on our side. Please try again.");
    expect(apiError.details).toBe("upstream failed");
  });
});

describe("extractTraceId helper", () => {
  it("returns trace id from ApiError instances", () => {
    const apiError = new ApiError(
      "failed",
      400,
      { trace_id: "nested-trace" },
      { traceId: "error-trace" }
    );
    expect(extractTraceId(apiError)).toBe("error-trace");
  });

  it("recurses into nested error envelopes", () => {
    const payload = {
      error: {
        details: {
          trace_id: "trace-456"
        }
      }
    };

    expect(extractTraceId(payload)).toBe("trace-456");
  });
});


