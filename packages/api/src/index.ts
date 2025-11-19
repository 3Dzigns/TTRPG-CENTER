import type {
  BillingLink,
  Character,
  CharacterCreateInput,
  CharacterUpdateInput,
  EffectiveQuota,
  Game,
  GameCreateInput,
  GameMember,
  GameMemberInviteInput,
  GameMemberUpdateInput,
  GameUpdateInput,
  Me,
  Source,
  UsageSummary,
  QueryRequestInput,
  QueryResponse,
  AdminHealthSnapshot,
  AdminAuditResponse,
  User,
  AdminSourceMutationRequest,
  AdminSourceMutationResult,
  AdminOverrideRequest,
  AdminOverrideResponse,
  UserProfileUpdateInput
} from "@ttrpg-center/types";

export interface ApiClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export interface RequestOptions extends RequestInit {
  query?: Record<string, string | number | boolean | undefined>;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly details?: unknown;
  public readonly traceId?: string;
  public readonly code?: string;

  constructor(
    message: string,
    status: number,
    details?: unknown,
    metadata: { traceId?: string; code?: string } = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.traceId = metadata.traceId;
    this.code = metadata.code;

    if (typeof (Error as any).captureStackTrace === "function") {
      (Error as any).captureStackTrace(this, ApiError);
    }
  }
}

const DEFAULT_HEADERS: HeadersInit = {
  "Content-Type": "application/json",
  Accept: "application/json"
};

const normalizeBaseUrl = (value?: string): string => {
  if (!value) {
    return "/api/v1";
  }

  const trimmed = value.trim();

  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed.replace(/\/+$/g, "");
  }

  if (!trimmed.startsWith("/")) {
    return `/${trimmed.replace(/^\/+/, "")}`;
  }

  return trimmed.replace(/\/+$/, "");
};

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl) ?? "/v1";

    const providedFetch = options.fetchImpl;
    const defaultFetch =
      typeof globalThis !== "undefined" && typeof globalThis.fetch === "function"
        ? globalThis.fetch
        : typeof fetch === "function"
          ? fetch
          : undefined;

    const baseFetch = providedFetch ?? defaultFetch;

    if (typeof baseFetch !== "function") {
      throw new Error("No fetch implementation is available for ApiClient.");
    }

    if (providedFetch) {
      this.fetchImpl = baseFetch;
      return;
    }

    this.fetchImpl = defaultFetch!.bind(globalThis) as typeof fetch;
  }

  async getMe(init?: RequestOptions): Promise<Me> {
    return this.request<Me>("/me", init);
  }

  async updateProfile(payload: UserProfileUpdateInput): Promise<Me> {
    return this.request<Me>("/me", {
      method: "PATCH",
      body: JSON.stringify(payload)
    });
  }

  async getGames(init?: RequestOptions): Promise<Game[]> {
    return this.request<Game[]>("/games", init);
  }

  async getGameById(id: string, init?: RequestOptions): Promise<Game> {
    return this.request<Game>(`/games/${id}`, init);
  }

  async createGame(payload: GameCreateInput): Promise<Game> {
    return this.request<Game>("/games", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async updateGame(id: string, payload: GameUpdateInput): Promise<Game> {
    return this.request<Game>(`/games/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    });
  }

  async deleteGame(id: string): Promise<void> {
    await this.request<void>(`/games/${id}`, { method: "DELETE" });
  }

  async addGameMember(
    gameId: string,
    payload: GameMemberInviteInput
  ): Promise<GameMember> {
    return this.request<GameMember>(`/games/${gameId}/members`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async updateGameMember(
    gameId: string,
    userId: string,
    payload: GameMemberUpdateInput
  ): Promise<GameMember> {
    return this.request<GameMember>(`/games/${gameId}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    });
  }

  async removeGameMember(gameId: string, userId: string): Promise<void> {
    await this.request<void>(`/games/${gameId}/members/${userId}`, {
      method: "DELETE"
    });
  }

  async addGameSource(
    gameId: string,
    sourceId: string
  ): Promise<Game> {
    return this.request<Game>(`/games/${gameId}/sources`, {
      method: "POST",
      body: JSON.stringify({ sourceId })
    });
  }

  async removeGameSource(
    gameId: string,
    sourceId: string
  ): Promise<Game> {
    return this.request<Game>(`/games/${gameId}/sources/${sourceId}`, {
      method: "DELETE"
    });
  }

  async joinGame(inviteCode: string): Promise<Game> {
    return this.request<Game>("/games/join", {
      method: "POST",
      body: JSON.stringify({ inviteCode })
    });
  }

  async getCharacters(
    query?: { userId?: string }
  ): Promise<Character[]> {
    return this.request<Character[]>("/characters", { query });
  }

  async createCharacter(
    payload: CharacterCreateInput
  ): Promise<Character> {
    return this.request<Character>("/characters", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async updateCharacter(
    id: string,
    payload: CharacterUpdateInput
  ): Promise<Character> {
    return this.request<Character>(`/characters/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    });
  }

  async getSources(
    query?: { owned?: boolean },
    init?: RequestOptions
  ): Promise<Source[]> {
    return this.request<Source[]>("/sources", { ...init, query });
  }

  async addUserSource(sourceId: string): Promise<Source[]> {
    return this.request<Source[]>("/sources", {
      method: "POST",
      body: JSON.stringify({ sourceId })
    });
  }

  async removeUserSource(sourceId: string): Promise<Source[]> {
    return this.request<Source[]>(`/sources/${sourceId}`, {
      method: "DELETE"
    });
  }

  async getUsers(): Promise<User[]> {
    return this.request<User[]>("/users");
  }

  async getAdminHealth(): Promise<AdminHealthSnapshot> {
    return this.request<AdminHealthSnapshot>("/admin/health");
  }

  async getAdminAudit(query?: {
    actor?: string;
    traceId?: string;
    cursor?: string;
    limit?: number;
  }): Promise<AdminAuditResponse> {
    return this.request<AdminAuditResponse>("/admin/audit", { query });
  }

  async mutateAdminSource(payload: AdminSourceMutationRequest): Promise<AdminSourceMutationResult> {
    return this.request<AdminSourceMutationResult>("/admin/source", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async submitAdminOverride(payload: AdminOverrideRequest): Promise<AdminOverrideResponse> {
    return this.request<AdminOverrideResponse>("/admin/override", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async getBillingLink(scope: "user" | "game", id: string): Promise<BillingLink> {
    return this.request<BillingLink>("/billing/link", {
      query: { scope, id }
    });
  }

  async getUsage(
    scope: "user" | "game",
    id: string
  ): Promise<UsageSummary> {
    return this.request<UsageSummary>("/usage", {
      query: { scope, id }
    });
  }

  async getQuotas(
    scope: "user" | "game",
    entityId: string
  ): Promise<EffectiveQuota> {
    return this.request<EffectiveQuota>("/quotas", {
      query: { scope, entityId }
    });
  }

  async submitQuery(payload: QueryRequestInput): Promise<QueryResponse> {
    return this.request<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  createEventsStream(path = "/events"): EventSource {
    if (typeof window === "undefined") {
      throw new Error("createEventsStream can only be used in the browser");
    }
    const url = this.buildUrl(path, {});
    return new EventSource(url, { withCredentials: true });
  }

  private async request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const { query = {}, ...rest } = init;

    const finalInit: RequestInit = {
      ...rest,
      headers: {
        ...DEFAULT_HEADERS,
        ...(rest.headers ?? {})
      },
      credentials: rest.credentials ?? "include"
    };

    const response = await this.fetchImpl(this.buildUrl(path, query), finalInit);

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      let rawBody: string | undefined;
      let parsedBody: unknown;

      if (contentType.includes("application/json")) {
        try {
          parsedBody = await response.json();
        } catch {
          rawBody = await response.text();
        }
      } else {
        rawBody = await response.text();
      }

      if (!parsedBody && rawBody) {
        try {
          parsedBody = JSON.parse(rawBody);
        } catch {
          parsedBody = rawBody;
        }
      }

      const headerTraceId = response.headers.get("x-trace-id") ?? undefined;
      let messageFromPayload: string | undefined;
      let traceIdFromPayload: string | undefined;
      let codeFromPayload: string | undefined;
      let errorDetails: unknown = parsedBody ?? rawBody;

      if (parsedBody && typeof parsedBody === "object") {
        const record = parsedBody as Record<string, unknown>;
        const envelopeError =
          record.error && typeof record.error === "object"
            ? (record.error as Record<string, unknown>)
            : undefined;

        if (envelopeError) {
          if (typeof envelopeError.message === "string") {
            messageFromPayload = envelopeError.message;
          }
          if (typeof envelopeError.trace_id === "string") {
            traceIdFromPayload = envelopeError.trace_id;
          } else if (typeof envelopeError.traceId === "string") {
            traceIdFromPayload = envelopeError.traceId;
          }
          if (typeof envelopeError.code === "string") {
            codeFromPayload = envelopeError.code;
          }
          if (envelopeError.details !== undefined) {
            errorDetails = envelopeError.details;
          }
        }

        if (!traceIdFromPayload) {
          if (typeof record.trace_id === "string") {
            traceIdFromPayload = record.trace_id;
          } else if (typeof record.traceId === "string") {
            traceIdFromPayload = record.traceId;
          }
        }

        if (!messageFromPayload && typeof record.message === "string") {
          messageFromPayload = record.message;
        }
      }

      const message =
        messageFromPayload ??
        (response.statusText && response.statusText !== ""
          ? response.statusText
          : this.defaultMessageForStatus(response.status));

      throw new ApiError(
        message,
        response.status,
        errorDetails,
        {
          traceId: traceIdFromPayload ?? headerTraceId,
          code: codeFromPayload
        }
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      return text as unknown as T;
    }
  }

  private defaultMessageForStatus(status: number): string {
    if (status === 401) {
      return "Please sign in again to continue.";
    }
    if (status === 403) {
      return "You do not have permission to perform this action.";
    }
    if (status === 404) {
      return "We couldn't find what you were looking for.";
    }
    if (status === 422) {
      return "Some of the provided information is invalid.";
    }
    if (status >= 500) {
      return "Something went wrong on our side. Please try again.";
    }
    return "We couldn't complete your request. Please try again.";
  }

  private buildUrl(
    path: string,
    query: Record<string, string | number | boolean | undefined>
  ): string {
    const normalizedBase = this.baseUrl.endsWith("/")
      ? this.baseUrl.slice(0, -1)
      : this.baseUrl;
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const searchParams = new URLSearchParams();

    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.set(key, String(value));
      }
    });

    const queryString = searchParams.toString();
    const baseWithPath = `${normalizedBase}${normalizedPath}`;

    if (queryString.length === 0) {
      return baseWithPath;
    }

    return `${baseWithPath}?${queryString}`;
  }
}

export const createApiClient = (options?: ApiClientOptions): ApiClient =>
  new ApiClient(options);

export { createEventStream, type EventStreamOptions, type EventStream, type EventPayload } from "./events";

export const extractTraceId = (input: unknown): string | undefined => {
  if (!input) {
    return undefined;
  }

  if (input instanceof ApiError) {
    return input.traceId ?? extractTraceId(input.details);
  }

  if (typeof input === "string") {
    try {
      const parsed = JSON.parse(input);
      return extractTraceId(parsed);
    } catch {
      return undefined;
    }
  }

  if (typeof input === "object") {
    const record = input as Record<string, unknown>;

    if (typeof record.trace_id === "string") {
      return record.trace_id;
    }

    if (typeof record.traceId === "string") {
      return record.traceId;
    }

    if (record.error) {
      const nested = extractTraceId(record.error);
      if (nested) {
        return nested;
      }
    }

    if (record.details) {
      return extractTraceId(record.details);
    }
  }

  return undefined;
};
