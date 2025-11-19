import { NextRequest, NextResponse } from "next/server";
import { and, eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { tierConfigs, quotaGrants, games } from "@/db/schema";
import type { EffectiveQuota, GameTier } from "@ttrpg-center/types";

/**
 * GET /api/v1/quotas?scope=game&entityId=xxx
 *
 * Calculates effective quotas for a user or game by combining:
 * - Base tier limits from tier_configs table
 * - Additional quotas from quota_grants table (purchases, promotions, etc.)
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const scope = searchParams.get("scope") as "user" | "game" | null;
    const entityId = searchParams.get("entityId");

    if (!scope || !entityId) {
      return NextResponse.json(
        { error: "Missing required parameters: scope, entityId" },
        { status: 400 }
      );
    }

    if (scope !== "user" && scope !== "game") {
      return NextResponse.json(
        { error: "Invalid scope. Must be 'user' or 'game'" },
        { status: 400 }
      );
    }

    // 1. Get the tier for this entity
    let tier: GameTier = "free"; // default

    if (scope === "game") {
      const game = await db.query.games.findFirst({
        where: eq(games.id, entityId)
      });

      if (!game) {
        return NextResponse.json(
          { error: "Game not found" },
          { status: 404 }
        );
      }

      tier = (game.tier ?? "free") as GameTier;
    }
    // For user scope, we'd need to add a tier column to auth_users table
    // For now, users default to "free" tier

    // 2. Get tier configuration from database
    const tierConfig = await db.query.tierConfigs.findFirst({
      where: eq(tierConfigs.tier, tier)
    });

    // Fallback to hardcoded defaults if tier config doesn't exist yet
    const baseLimits = tierConfig ?? {
      tier,
      baseSourceLimit: tier === "free" ? 3 : tier === "standard" ? 10 : 999,
      baseTextAssistLimit: tier === "free" ? 100 : tier === "standard" ? 1000 : 9999,
      baseAutomationCreditsLimit: tier === "free" ? 10 : tier === "standard" ? 100 : 999,
      baseAudioBridgeLimit: tier === "free" ? 0 : tier === "standard" ? 60 : 999,
      baseDiscordBridgeLimit: tier === "free" ? 0 : tier === "standard" ? 100 : 999,
      allowAudioBridge: tier !== "free",
      allowSummaries: tier !== "free",
      allowDiscordBridge: tier !== "free"
    };

    // 3. Get all active quota grants for this entity
    const now = new Date();
    const grants = await db
      .select()
      .from(quotaGrants)
      .where(
        and(
          eq(quotaGrants.scope, scope),
          eq(quotaGrants.entityId, entityId),
          eq(quotaGrants.isActive, true)
        )
      );

    // Filter out expired grants
    const activeGrants = grants.filter(grant => {
      if (!grant.expiresAt) return true; // No expiration
      return new Date(grant.expiresAt) > now;
    });

    // 4. Calculate additional quotas from grants
    const additionalSources = activeGrants.reduce((sum, grant) => sum + grant.additionalSources, 0);
    const additionalTextAssist = activeGrants.reduce((sum, grant) => sum + grant.additionalTextAssist, 0);
    const additionalAutomationCredits = activeGrants.reduce((sum, grant) => sum + grant.additionalAutomationCredits, 0);
    const additionalAudioBridge = activeGrants.reduce((sum, grant) => sum + grant.additionalAudioBridge, 0);
    const additionalDiscordBridge = activeGrants.reduce((sum, grant) => sum + grant.additionalDiscordBridge, 0);

    // 5. Build effective quota response
    const effectiveQuota: EffectiveQuota = {
      scope,
      entityId,
      tier,

      // Sources
      baseSourceLimit: baseLimits.baseSourceLimit,
      additionalSourcesFromGrants: additionalSources,
      effectiveSourceLimit: baseLimits.baseSourceLimit + additionalSources,

      // Text assist
      baseTextAssistLimit: baseLimits.baseTextAssistLimit,
      additionalTextAssistFromGrants: additionalTextAssist,
      effectiveTextAssistLimit: baseLimits.baseTextAssistLimit + additionalTextAssist,

      // Automation credits
      baseAutomationCreditsLimit: baseLimits.baseAutomationCreditsLimit,
      additionalAutomationCreditsFromGrants: additionalAutomationCredits,
      effectiveAutomationCreditsLimit: baseLimits.baseAutomationCreditsLimit + additionalAutomationCredits,

      // Audio bridge
      baseAudioBridgeLimit: baseLimits.baseAudioBridgeLimit,
      additionalAudioBridgeFromGrants: additionalAudioBridge,
      effectiveAudioBridgeLimit: baseLimits.baseAudioBridgeLimit + additionalAudioBridge,

      // Discord bridge
      baseDiscordBridgeLimit: baseLimits.baseDiscordBridgeLimit,
      additionalDiscordBridgeFromGrants: additionalDiscordBridge,
      effectiveDiscordBridgeLimit: baseLimits.baseDiscordBridgeLimit + additionalDiscordBridge,

      // Feature flags
      allowAudioBridge: baseLimits.allowAudioBridge,
      allowSummaries: baseLimits.allowSummaries,
      allowDiscordBridge: baseLimits.allowDiscordBridge,

      // Metadata
      activeGrants: activeGrants.map(grant => ({
        id: grant.id,
        scope: grant.scope as "user" | "game",
        entityId: grant.entityId,
        grantType: grant.grantType as "purchase" | "promotion" | "manual" | "referral",
        additionalSources: grant.additionalSources,
        additionalTextAssist: grant.additionalTextAssist,
        additionalAutomationCredits: grant.additionalAutomationCredits,
        additionalAudioBridge: grant.additionalAudioBridge,
        additionalDiscordBridge: grant.additionalDiscordBridge,
        grantedBy: grant.grantedBy ?? undefined,
        grantedAt: grant.grantedAt.toISOString(),
        expiresAt: grant.expiresAt?.toISOString(),
        reason: grant.reason ?? undefined,
        isActive: grant.isActive
      })),
      calculatedAt: new Date().toISOString()
    };

    return NextResponse.json(effectiveQuota);
  } catch (error) {
    console.error("Error fetching quotas:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
