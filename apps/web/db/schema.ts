import {
  boolean,
  integer,
  jsonb,
  pgEnum,
  pgTable,
  primaryKey,
  serial,
  text,
  timestamp,
  uuid
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

export const roleNameEnum = pgEnum("auth_role_name", ["player", "gm", "admin"]);

export const authUsers = pgTable("auth_users", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: text("email").notNull().unique(),
  displayName: text("display_name").notNull(),
  avatarUrl: text("avatar_url"),
  preferredTheme: text("preferred_theme").notNull().default("system"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  lastLoginAt: timestamp("last_login_at", { withTimezone: true })
});

export const authRoles = pgTable("auth_roles", {
  id: serial("id").primaryKey(),
  name: roleNameEnum("name").notNull().unique(),
  description: text("description")
});

export const authUserRoles = pgTable(
  "auth_user_roles",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
    roleId: integer("role_id")
      .notNull()
      .references(() => authRoles.id, { onDelete: "cascade", onUpdate: "cascade" }),
    grantedAt: timestamp("granted_at", { withTimezone: true }).notNull().defaultNow(),
    grantedBy: uuid("granted_by")
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.roleId] })
  })
);

export const authOauthAccounts = pgTable("auth_oauth_accounts", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
  provider: text("provider").notNull(),
  providerAccountId: text("provider_account_id").notNull(),
  accessToken: text("access_token"),
  refreshToken: text("refresh_token"),
  expiresAt: timestamp("expires_at", { withTimezone: true }),
  rawProfile: jsonb("raw_profile"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow()
});

export const authSessions = pgTable("auth_sessions", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
  sessionTokenHash: text("session_token_hash").notNull().unique(),
  userAgent: text("user_agent"),
  ipAddress: text("ip_address"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  revokedAt: timestamp("revoked_at", { withTimezone: true }),
  isRevoked: boolean("is_revoked").notNull().default(false)
});

export type AuthRoleName = (typeof roleNameEnum.enumValues)[number];

export const authUsersRelations = relations(authUsers, ({ many }) => ({
  roles: many(authUserRoles),
  sessions: many(authSessions),
  oauthAccounts: many(authOauthAccounts)
}));

export const authRolesRelations = relations(authRoles, ({ many }) => ({
  assignments: many(authUserRoles)
}));

export const authUserRolesRelations = relations(authUserRoles, ({ one }) => ({
  user: one(authUsers, {
    fields: [authUserRoles.userId],
    references: [authUsers.id]
  }),
  role: one(authRoles, {
    fields: [authUserRoles.roleId],
    references: [authRoles.id]
  })
}));

export const authSessionsRelations = relations(authSessions, ({ one }) => ({
  user: one(authUsers, {
    fields: [authSessions.userId],
    references: [authUsers.id]
  })
}));

export const authOauthAccountsRelations = relations(authOauthAccounts, ({ one }) => ({
  user: one(authUsers, {
    fields: [authOauthAccounts.userId],
    references: [authUsers.id]
  })
}));

// =====================================================
// GAMES AND CONTENT TABLES
// =====================================================

// Type definitions for enums (using TypeScript types, not PostgreSQL enums)
export type GameStatus = "draft" | "active" | "archived";
export type GameTier = "free" | "standard" | "premium";
export type GameMemberRole = "gm" | "co-gm" | "player" | "spectator";
export type GameMemberStatus = "active" | "invited" | "removed";
export type CharacterSystem = "dnd-5e" | "pf2e" | "cyberpunk-red" | "generic" | "custom";
export type SourceCategory = "campaign" | "module" | "expansion" | "ruleset" | "homebrew";
export type UsageScope = "user" | "game";

// Games table
export const games = pgTable("games", {
  id: uuid("id").defaultRandom().primaryKey(),
  title: text("title").notNull(),
  summary: text("summary"),
  status: text("status").notNull().default("draft").$type<GameStatus>(),
  gmId: uuid("gm_id")
    .notNull()
    .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
  sessionCount: integer("session_count").notNull().default(0),
  lastPlayedAt: timestamp("last_played_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  inviteCode: text("invite_code").unique(),
  tier: text("tier").notNull().default("free").$type<GameTier>(),
  allowAudioBridge: boolean("allow_audio_bridge").notNull().default(false),
  allowSummaries: boolean("allow_summaries").notNull().default(false),
  allowDiscordBridge: boolean("allow_discord_bridge").notNull().default(false)
});

// Game members (many-to-many: users <-> games)
export const gameMembers = pgTable(
  "game_members",
  {
    gameId: uuid("game_id")
      .notNull()
      .references(() => games.id, { onDelete: "cascade", onUpdate: "cascade" }),
    userId: uuid("user_id")
      .notNull()
      .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
    role: text("role").notNull().default("player").$type<GameMemberRole>(),
    status: text("status").notNull().default("active").$type<GameMemberStatus>(),
    invitedAt: timestamp("invited_at", { withTimezone: true }),
    joinedAt: timestamp("joined_at", { withTimezone: true }).defaultNow()
  },
  (table) => ({
    pk: primaryKey({ columns: [table.gameId, table.userId] })
  })
);

// Characters table
export const characters = pgTable("characters", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull(),
  className: text("class_name").notNull(),
  level: integer("level").notNull().default(1),
  ownerId: uuid("owner_id")
    .notNull()
    .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
  portraitUrl: text("portrait_url"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  system: text("system").notNull().default("dnd-5e").$type<CharacterSystem>(),
  gameId: uuid("game_id").references(() => games.id, { onDelete: "set null" })
});

// Sources table
export const sources = pgTable("sources", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull().unique(),
  category: text("category").notNull().default("module").$type<SourceCategory>(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow()
});

// User sources (many-to-many: users <-> sources)
export const userSources = pgTable(
  "user_sources",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => authUsers.id, { onDelete: "cascade", onUpdate: "cascade" }),
    sourceId: uuid("source_id")
      .notNull()
      .references(() => sources.id, { onDelete: "cascade", onUpdate: "cascade" }),
    acquiredAt: timestamp("acquired_at", { withTimezone: true }).notNull().defaultNow()
  },
  (table) => ({
    pk: primaryKey({ columns: [table.userId, table.sourceId] })
  })
);

// Game sources (many-to-many: games <-> sources)
export const gameSources = pgTable(
  "game_sources",
  {
    gameId: uuid("game_id")
      .notNull()
      .references(() => games.id, { onDelete: "cascade", onUpdate: "cascade" }),
    sourceId: uuid("source_id")
      .notNull()
      .references(() => sources.id, { onDelete: "cascade", onUpdate: "cascade" }),
    addedAt: timestamp("added_at", { withTimezone: true }).notNull().defaultNow()
  },
  (table) => ({
    pk: primaryKey({ columns: [table.gameId, table.sourceId] })
  })
);

// Character sources (many-to-many: characters <-> sources)
export const characterSources = pgTable(
  "character_sources",
  {
    characterId: uuid("character_id")
      .notNull()
      .references(() => characters.id, { onDelete: "cascade", onUpdate: "cascade" }),
    sourceId: uuid("source_id")
      .notNull()
      .references(() => sources.id, { onDelete: "cascade", onUpdate: "cascade" }),
    addedAt: timestamp("added_at", { withTimezone: true }).notNull().defaultNow()
  },
  (table) => ({
    pk: primaryKey({ columns: [table.characterId, table.sourceId] })
  })
);

// Usage metrics table
export const usageMetrics = pgTable("usage_metrics", {
  id: uuid("id").defaultRandom().primaryKey(),
  scope: text("scope").notNull().$type<UsageScope>(),
  entityId: uuid("entity_id").notNull(),
  totalSecondsPlayed: integer("total_seconds_played").notNull().default(0),
  monthlySessionCount: integer("monthly_session_count").notNull().default(0),
  automationCreditsRemaining: integer("automation_credits_remaining").notNull().default(0),
  textAssistRemaining: integer("text_assist_remaining"),
  audioBridgeRemaining: integer("audio_bridge_remaining"),
  discordBridgeRemaining: integer("discord_bridge_remaining"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow()
});

// Tier configuration table - defines base limits for each tier
export const tierConfigs = pgTable("tier_configs", {
  tier: text("tier").notNull().primaryKey().$type<GameTier>(),
  displayName: text("display_name").notNull(),
  baseSourceLimit: integer("base_source_limit").notNull().default(0),
  baseTextAssistLimit: integer("base_text_assist_limit").notNull().default(0),
  baseAutomationCreditsLimit: integer("base_automation_credits_limit").notNull().default(0),
  baseAudioBridgeLimit: integer("base_audio_bridge_limit").notNull().default(0),
  baseDiscordBridgeLimit: integer("base_discord_bridge_limit").notNull().default(0),
  allowAudioBridge: boolean("allow_audio_bridge").notNull().default(false),
  allowSummaries: boolean("allow_summaries").notNull().default(false),
  allowDiscordBridge: boolean("allow_discord_bridge").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow()
});

// Quota grants - tracks additional quotas granted to accounts (purchases, promotions, etc.)
export const quotaGrants = pgTable("quota_grants", {
  id: uuid("id").defaultRandom().primaryKey(),
  scope: text("scope").notNull().$type<UsageScope>(),
  entityId: uuid("entity_id").notNull(),
  grantType: text("grant_type").notNull(), // 'purchase', 'promotion', 'manual', 'referral'
  additionalSources: integer("additional_sources").notNull().default(0),
  additionalTextAssist: integer("additional_text_assist").notNull().default(0),
  additionalAutomationCredits: integer("additional_automation_credits").notNull().default(0),
  additionalAudioBridge: integer("additional_audio_bridge").notNull().default(0),
  additionalDiscordBridge: integer("additional_discord_bridge").notNull().default(0),
  grantedBy: uuid("granted_by").references(() => authUsers.id),
  grantedAt: timestamp("granted_at", { withTimezone: true }).notNull().defaultNow(),
  expiresAt: timestamp("expires_at", { withTimezone: true }),
  reason: text("reason"),
  isActive: boolean("is_active").notNull().default(true)
});

// =====================================================
// RELATIONS
// =====================================================

export const gamesRelations = relations(games, ({ one, many }) => ({
  gm: one(authUsers, {
    fields: [games.gmId],
    references: [authUsers.id]
  }),
  members: many(gameMembers),
  sources: many(gameSources),
  characters: many(characters)
}));

export const gameMembersRelations = relations(gameMembers, ({ one }) => ({
  game: one(games, {
    fields: [gameMembers.gameId],
    references: [games.id]
  }),
  user: one(authUsers, {
    fields: [gameMembers.userId],
    references: [authUsers.id]
  })
}));

export const charactersRelations = relations(characters, ({ one, many }) => ({
  owner: one(authUsers, {
    fields: [characters.ownerId],
    references: [authUsers.id]
  }),
  game: one(games, {
    fields: [characters.gameId],
    references: [games.id]
  }),
  sources: many(characterSources)
}));

export const sourcesRelations = relations(sources, ({ many }) => ({
  userSources: many(userSources),
  gameSources: many(gameSources),
  characterSources: many(characterSources)
}));

export const userSourcesRelations = relations(userSources, ({ one }) => ({
  user: one(authUsers, {
    fields: [userSources.userId],
    references: [authUsers.id]
  }),
  source: one(sources, {
    fields: [userSources.sourceId],
    references: [sources.id]
  })
}));

export const gameSourcesRelations = relations(gameSources, ({ one }) => ({
  game: one(games, {
    fields: [gameSources.gameId],
    references: [games.id]
  }),
  source: one(sources, {
    fields: [gameSources.sourceId],
    references: [sources.id]
  })
}));

export const characterSourcesRelations = relations(characterSources, ({ one }) => ({
  character: one(characters, {
    fields: [characterSources.characterId],
    references: [characters.id]
  }),
  source: one(sources, {
    fields: [characterSources.sourceId],
    references: [sources.id]
  })
}));

// Type exports
export type Game = typeof games.$inferSelect;
export type NewGame = typeof games.$inferInsert;
export type Character = typeof characters.$inferSelect;
export type NewCharacter = typeof characters.$inferInsert;
export type Source = typeof sources.$inferSelect;
export type NewSource = typeof sources.$inferInsert;
export type GameMember = typeof gameMembers.$inferSelect;
export type NewGameMember = typeof gameMembers.$inferInsert;
export type UsageMetric = typeof usageMetrics.$inferSelect;
export type NewUsageMetric = typeof usageMetrics.$inferInsert;
export type TierConfig = typeof tierConfigs.$inferSelect;
export type NewTierConfig = typeof tierConfigs.$inferInsert;
export type QuotaGrant = typeof quotaGrants.$inferSelect;
export type NewQuotaGrant = typeof quotaGrants.$inferInsert;
