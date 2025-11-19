export type UserRole = "player" | "gm" | "admin";

export interface User {
  id: string;
  displayName: string;
  email: string;
  roles: UserRole[];
  avatarUrl?: string | null;
}

export type CharacterSystem =
  | "dnd-5e"
  | "pf2e"
  | "cyberpunk-red"
  | "generic"
  | "custom";

export interface Character {
  id: string;
  name: string;
  className: string;
  level: number;
  ownerId: string;
  portraitUrl?: string;
  createdAt: string;
  updatedAt: string;
  system: CharacterSystem;
  activeSourceIds?: string[];
  gameId?: string | null;
}

export type GameStatus = "draft" | "active" | "archived";

export type GameTier = "free" | "standard" | "premium";

export type GameMemberRole = "gm" | "co-gm" | "player" | "spectator";

export type GameMemberStatus = "active" | "invited" | "removed";

export interface GameMember {
  userId: string;
  email: string;
  displayName: string;
  role: GameMemberRole;
  status: GameMemberStatus;
  invitedAt?: string;
  joinedAt?: string;
}

export interface Game {
  id: string;
  title: string;
  summary?: string;
  status: GameStatus;
  gmId: string;
  playerIds: string[];
  sessionCount: number;
  lastPlayedAt?: string;
  createdAt: string;
  updatedAt: string;
  inviteCode?: string;
  sourceIds?: string[];
  sources?: Source[];
  tier?: GameTier;
  members?: GameMember[];
  allowAudioBridge?: boolean;
  allowSummaries?: boolean;
  allowDiscordBridge?: boolean;
}

export type SourceCategory =
  | "campaign"
  | "module"
  | "expansion"
  | "ruleset"
  | "homebrew";

export interface Source {
  id: string;
  name: string;
  category: SourceCategory;
  owned: boolean;
  updatedAt: string;
}

export interface UsageMeter {
  totalSecondsPlayed: number;
  monthlySessionCount: number;
  automationCreditsRemaining: number;
  textAssistRemaining?: number;
  audioBridgeRemaining?: number;
  discordBridgeRemaining?: number;
}

export interface BillingLink {
  url: string;
  expiresAt: string;
  label: string;
}

export interface Me extends User {
  preferredTheme: "light" | "dark" | "system";
  usage: UsageMeter;
  billing?: BillingLink;
}

export interface UserProfileUpdateInput {
  displayName?: string;
  email?: string;
  avatarUrl?: string | null;
  preferredTheme?: "light" | "dark" | "system";
  roles?: UserRole[];
}

export interface PaginatedResponse<T> {
  data: T[];
  page: number;
  pageSize: number;
  total: number;
}

export type ServiceHealthStatus = "healthy" | "degraded" | "down";

export interface AdminServiceHealth {
  id: string;
  name: string;
  status: ServiceHealthStatus;
  lastCheckedAt: string;
  message?: string;
  region?: string;
}

export interface AdminHealthSnapshot {
  services: AdminServiceHealth[];
  updatedAt: string;
}

export interface AdminAuditEntry {
  id: string;
  actor: string;
  traceId: string;
  action: string;
  scope: string;
  summary?: string;
  createdAt: string;
  metadata?: Record<string, unknown>;
}

export interface AdminAuditResponse {
  entries: AdminAuditEntry[];
  nextCursor?: string | null;
}

export type AdminSourceMutationAction = "create" | "update" | "delete";

export interface AdminSourceMutationRequest {
  action: AdminSourceMutationAction;
  source: {
    id?: string;
    name: string;
    category: SourceCategory;
    owned?: boolean;
  };
}

export interface AdminSourceMutationResult {
  traceId: string;
  action: AdminSourceMutationAction;
  source: Source;
}

export type AdminOverrideTarget = "cassandra" | "mongo" | "neo4j";

export interface AdminOverrideRequest {
  target: AdminOverrideTarget;
  recordPath: string;
  payload: Record<string, unknown>;
  reason?: string;
  sourceId?: string;
}

export interface AdminOverrideResponse {
  traceId: string;
  status: "accepted";
}

export interface AdminOverrideEvent {
  type: "admin_override";
  traceId: string;
  target: AdminOverrideTarget;
  sourceId?: string;
  actor: string;
  diff?: Record<string, unknown>;
  createdAt: string;
}

export interface CharacterCreateInput {
  name: string;
  className: string;
  level: number;
  system: CharacterSystem;
}

export interface CharacterUpdateInput {
  name?: string;
  className?: string;
  level?: number;
  system?: CharacterSystem;
  gameId?: string | null;
  activeSourceIds?: string[];
}

export interface GameCreateInput {
  title: string;
  summary?: string;
  tier?: GameTier;
}

export interface GameUpdateInput {
  title?: string;
  summary?: string;
  status?: GameStatus;
  tier?: GameTier;
  allowAudioBridge?: boolean;
  allowSummaries?: boolean;
  allowDiscordBridge?: boolean;
}

export interface GameMemberInviteInput {
  email?: string;
  userId?: string;
  role: GameMemberRole;
}

export interface GameMemberUpdateInput {
  role: GameMemberRole;
}

export interface UsageSummary {
  scope: "user" | "game";
  id: string;
  meter: UsageMeter;
  updatedAt: string;
}

// Tier configuration
export interface TierConfig {
  tier: GameTier;
  displayName: string;
  baseSourceLimit: number;
  baseTextAssistLimit: number;
  baseAutomationCreditsLimit: number;
  baseAudioBridgeLimit: number;
  baseDiscordBridgeLimit: number;
  allowAudioBridge: boolean;
  allowSummaries: boolean;
  allowDiscordBridge: boolean;
  createdAt: string;
  updatedAt: string;
}

// Quota grants (add-ons, purchases, promotions)
export type QuotaGrantType = "purchase" | "promotion" | "manual" | "referral";

export interface QuotaGrant {
  id: string;
  scope: "user" | "game";
  entityId: string;
  grantType: QuotaGrantType;
  additionalSources: number;
  additionalTextAssist: number;
  additionalAutomationCredits: number;
  additionalAudioBridge: number;
  additionalDiscordBridge: number;
  grantedBy?: string;
  grantedAt: string;
  expiresAt?: string;
  reason?: string;
  isActive: boolean;
}

// Effective quotas (base tier + add-ons)
export interface EffectiveQuota {
  scope: "user" | "game";
  entityId: string;
  tier: GameTier;

  // Source limits breakdown
  baseSourceLimit: number;
  additionalSourcesFromGrants: number;
  effectiveSourceLimit: number;

  // Text assist limits
  baseTextAssistLimit: number;
  additionalTextAssistFromGrants: number;
  effectiveTextAssistLimit: number;

  // Automation credits
  baseAutomationCreditsLimit: number;
  additionalAutomationCreditsFromGrants: number;
  effectiveAutomationCreditsLimit: number;

  // Audio bridge
  baseAudioBridgeLimit: number;
  additionalAudioBridgeFromGrants: number;
  effectiveAudioBridgeLimit: number;

  // Discord bridge
  baseDiscordBridgeLimit: number;
  additionalDiscordBridgeFromGrants: number;
  effectiveDiscordBridgeLimit: number;

  // Feature flags
  allowAudioBridge: boolean;
  allowSummaries: boolean;
  allowDiscordBridge: boolean;

  // Metadata
  activeGrants: QuotaGrant[];
  calculatedAt: string;
}

export * from "./query-contract";
