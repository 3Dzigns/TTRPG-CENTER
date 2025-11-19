import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { usageMetrics } from "@/db/schema";
import { eq, and } from "drizzle-orm";
import type { UsageSummary, UsageMeter } from "@ttrpg-center/types";

export async function GET(request: NextRequest) {
  try {
    const scope = request.nextUrl.searchParams.get("scope") ?? "user";
    const id = request.nextUrl.searchParams.get("id");

    if (!id) {
      return NextResponse.json(
        { error: "Missing required parameter: id" },
        { status: 400 }
      );
    }

    const scopeValue = scope === "game" ? "game" : "user";

    const result = await db
      .select()
      .from(usageMetrics)
      .where(
        and(
          eq(usageMetrics.scope, scopeValue),
          eq(usageMetrics.entityId, id)
        )
      )
      .limit(1);

    if (result.length === 0) {
      // Return default usage metrics for new entities
      const defaultMeter: UsageMeter = {
        totalSecondsPlayed: 0,
        monthlySessionCount: 0,
        automationCreditsRemaining: 0,
        textAssistRemaining: scope === "user" ? 10 : 5,
        audioBridgeRemaining: scope === "user" ? 5 : undefined,
        discordBridgeRemaining: scope === "user" ? 8 : undefined
      };

      const defaultSummary: UsageSummary = {
        scope: scopeValue,
        id,
        meter: defaultMeter,
        updatedAt: new Date().toISOString()
      };

      return NextResponse.json(defaultSummary);
    }

    const record = result[0];

    const usageSummary: UsageSummary = {
      scope: scopeValue,
      id: record.entityId,
      meter: {
        totalSecondsPlayed: record.totalSecondsPlayed,
        monthlySessionCount: record.monthlySessionCount,
        automationCreditsRemaining: record.automationCreditsRemaining,
        textAssistRemaining: record.textAssistRemaining ?? undefined,
        audioBridgeRemaining: record.audioBridgeRemaining ?? undefined,
        discordBridgeRemaining: record.discordBridgeRemaining ?? undefined
      },
      updatedAt: record.updatedAt.toISOString()
    };

    return NextResponse.json(usageSummary);
  } catch (error) {
    console.error("Error fetching usage metrics:", error);
    return NextResponse.json(
      { error: "Failed to fetch usage metrics" },
      { status: 500 }
    );
  }
}

