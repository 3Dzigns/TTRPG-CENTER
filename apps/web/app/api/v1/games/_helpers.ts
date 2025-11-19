import { db } from "@/lib/db";
import {
  games,
  gameMembers,
  gameSources,
  authUsers,
  sources as sourcesTable,
  tierConfigs,
  quotaGrants
} from "@/db/schema";
import type { Game, GameMember, GameTier, Source } from "@ttrpg-center/types";
import { and, eq } from "drizzle-orm";

export type GameRow = typeof games.$inferSelect;

const DEFAULT_SOURCE_LIMITS: Record<GameTier, number> = {
  free: 3,
  standard: 10,
  premium: 999
};

export async function hydrateGame(gameRecord: GameRow): Promise<Game> {
  const membersData = await db
    .select({
      userId: gameMembers.userId,
      role: gameMembers.role,
      status: gameMembers.status,
      invitedAt: gameMembers.invitedAt,
      joinedAt: gameMembers.joinedAt,
      email: authUsers.email,
      displayName: authUsers.displayName
    })
    .from(gameMembers)
    .innerJoin(authUsers, eq(gameMembers.userId, authUsers.id))
    .where(eq(gameMembers.gameId, gameRecord.id));

  const members: GameMember[] = membersData.map((member) => ({
    userId: member.userId,
    email: member.email,
    displayName: member.displayName,
    role: member.role as GameMember["role"],
    status: member.status as GameMember["status"],
    invitedAt: member.invitedAt?.toISOString(),
    joinedAt: member.joinedAt?.toISOString()
  }));

  const sourcesData = await db
    .select({
      id: sourcesTable.id,
      name: sourcesTable.name,
      category: sourcesTable.category,
      updatedAt: sourcesTable.updatedAt
    })
    .from(gameSources)
    .innerJoin(sourcesTable, eq(gameSources.sourceId, sourcesTable.id))
    .where(eq(gameSources.gameId, gameRecord.id));

  const sources: Source[] = sourcesData.map((source) => ({
    id: source.id,
    name: source.name,
    category: source.category,
    owned: false,
    updatedAt: source.updatedAt.toISOString()
  }));

  const playerIds = members
    .filter((member) => member.status === "active" && member.role !== "spectator")
    .map((member) => member.userId);

  return {
    id: gameRecord.id,
    title: gameRecord.title,
    summary: gameRecord.summary ?? undefined,
    status: gameRecord.status,
    gmId: gameRecord.gmId,
    playerIds,
    sessionCount: gameRecord.sessionCount,
    lastPlayedAt: gameRecord.lastPlayedAt?.toISOString(),
    createdAt: gameRecord.createdAt.toISOString(),
    updatedAt: gameRecord.updatedAt.toISOString(),
    inviteCode: gameRecord.inviteCode ?? undefined,
    sourceIds: sources.map((source) => source.id),
    sources,
    tier: gameRecord.tier ?? undefined,
    members,
    allowAudioBridge: gameRecord.allowAudioBridge ?? undefined,
    allowSummaries: gameRecord.allowSummaries ?? undefined,
    allowDiscordBridge: gameRecord.allowDiscordBridge ?? undefined
  };
}

export async function fetchGameWithRelations(gameId: string): Promise<Game | null> {
  const gameRecord = await db.query.games.findFirst({
    where: eq(games.id, gameId)
  });
  if (!gameRecord) {
    return null;
  }
  return hydrateGame(gameRecord);
}

export async function getGameSourceLimit(gameRecord: GameRow): Promise<number> {
  const tier = (gameRecord.tier ?? "free") as GameTier;
  const tierConfig = await db.query.tierConfigs.findFirst({
    where: eq(tierConfigs.tier, tier)
  });
  const baseLimit = tierConfig?.baseSourceLimit ?? DEFAULT_SOURCE_LIMITS[tier];

  const grantRows = await db
    .select({
      additionalSources: quotaGrants.additionalSources,
      expiresAt: quotaGrants.expiresAt,
      isActive: quotaGrants.isActive
    })
    .from(quotaGrants)
    .where(
      and(
        eq(quotaGrants.scope, "game"),
        eq(quotaGrants.entityId, gameRecord.id),
        eq(quotaGrants.isActive, true)
      )
    );

  const now = new Date();
  const bonus = grantRows
    .filter((grant) => !grant.expiresAt || grant.expiresAt > now)
    .reduce((sum, grant) => sum + grant.additionalSources, 0);

  return baseLimit + bonus;
}
