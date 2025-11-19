import type { BillingLink, Character, CharacterCreateInput, CharacterUpdateInput, EffectiveQuota, Game, GameCreateInput, GameMember, GameMemberInviteInput, GameMemberUpdateInput, GameUpdateInput, Me, Source, UsageSummary, QueryRequestInput, QueryResponse, AdminHealthSnapshot, AdminAuditResponse, User, AdminSourceMutationRequest, AdminSourceMutationResult, AdminOverrideRequest, AdminOverrideResponse, UserProfileUpdateInput } from "@ttrpg-center/types";
export interface ApiClientOptions {
    baseUrl?: string;
    fetchImpl?: typeof fetch;
}
export interface RequestOptions extends RequestInit {
    query?: Record<string, string | number | boolean | undefined>;
}
export declare class ApiError extends Error {
    readonly status: number;
    readonly details?: unknown;
    readonly traceId?: string;
    readonly code?: string;
    constructor(message: string, status: number, details?: unknown, metadata?: {
        traceId?: string;
        code?: string;
    });
}
export declare class ApiClient {
    private readonly baseUrl;
    private readonly fetchImpl;
    constructor(options?: ApiClientOptions);
    getMe(init?: RequestOptions): Promise<Me>;
    updateProfile(payload: UserProfileUpdateInput): Promise<Me>;
    getGames(init?: RequestOptions): Promise<Game[]>;
    getGameById(id: string, init?: RequestOptions): Promise<Game>;
    createGame(payload: GameCreateInput): Promise<Game>;
    updateGame(id: string, payload: GameUpdateInput): Promise<Game>;
    deleteGame(id: string): Promise<void>;
    addGameMember(gameId: string, payload: GameMemberInviteInput): Promise<GameMember>;
    updateGameMember(gameId: string, userId: string, payload: GameMemberUpdateInput): Promise<GameMember>;
    removeGameMember(gameId: string, userId: string): Promise<void>;
    addGameSource(gameId: string, sourceId: string): Promise<Game>;
    removeGameSource(gameId: string, sourceId: string): Promise<Game>;
    joinGame(inviteCode: string): Promise<Game>;
    getCharacters(query?: {
        userId?: string;
    }): Promise<Character[]>;
    createCharacter(payload: CharacterCreateInput): Promise<Character>;
    updateCharacter(id: string, payload: CharacterUpdateInput): Promise<Character>;
    getSources(query?: {
        owned?: boolean;
    }, init?: RequestOptions): Promise<Source[]>;
    getUsers(): Promise<User[]>;
    getAdminHealth(): Promise<AdminHealthSnapshot>;
    getAdminAudit(query?: {
        actor?: string;
        traceId?: string;
        cursor?: string;
        limit?: number;
    }): Promise<AdminAuditResponse>;
    mutateAdminSource(payload: AdminSourceMutationRequest): Promise<AdminSourceMutationResult>;
    submitAdminOverride(payload: AdminOverrideRequest): Promise<AdminOverrideResponse>;
    getBillingLink(scope: "user" | "game", id: string): Promise<BillingLink>;
    getUsage(scope: "user" | "game", id: string): Promise<UsageSummary>;
    getQuotas(scope: "user" | "game", entityId: string): Promise<EffectiveQuota>;
    submitQuery(payload: QueryRequestInput): Promise<QueryResponse>;
    createEventsStream(path?: string): EventSource;
    private request;
    private defaultMessageForStatus;
    private buildUrl;
}
export declare const createApiClient: (options?: ApiClientOptions) => ApiClient;
export { createEventStream, type EventStreamOptions, type EventStream, type EventPayload } from "./events";
export declare const extractTraceId: (input: unknown) => string | undefined;
