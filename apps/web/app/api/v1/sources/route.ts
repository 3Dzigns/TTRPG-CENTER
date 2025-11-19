import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { sources, userSources } from "@/db/schema";
import { and, eq } from "drizzle-orm";
import type { Source } from "@ttrpg-center/types";
import { getAuthenticatedSession } from "@/lib/auth/server-session";

export async function GET(request: NextRequest) {
  try {
    const ownedFilter = request.nextUrl.searchParams.get("owned");
    const shouldFilterOwned = ownedFilter === "true";

    // Get authenticated user session
    const session = await getAuthenticatedSession(request);

    // Get all sources
    const allSources = await db.select().from(sources);

    if (shouldFilterOwned && session) {
      // Get user's owned sources
      const ownedSources = await db
        .select({ sourceId: userSources.sourceId })
        .from(userSources)
        .where(eq(userSources.userId, session.user.id));

      const ownedSourceIds = new Set(ownedSources.map((s) => s.sourceId));

      const data: Source[] = allSources.map((source) => ({
        id: source.id,
        name: source.name,
        category: source.category,
        owned: ownedSourceIds.has(source.id),
        updatedAt: source.updatedAt.toISOString()
      }));

      // Only return sources the user actually owns
      return NextResponse.json(data.filter((s) => s.owned));
    } else if (session) {
      // Show all sources with ownership status
      const ownedSources = await db
        .select({ sourceId: userSources.sourceId })
        .from(userSources)
        .where(eq(userSources.userId, session.user.id));

      const ownedSourceIds = new Set(ownedSources.map((s) => s.sourceId));

      const data: Source[] = allSources.map((source) => ({
        id: source.id,
        name: source.name,
        category: source.category,
        owned: ownedSourceIds.has(source.id),
        updatedAt: source.updatedAt.toISOString()
      }));

      return NextResponse.json(data);
    } else {
      // No user context, return all sources without ownership
      const data: Source[] = allSources.map((source) => ({
        id: source.id,
        name: source.name,
        category: source.category,
        owned: false,
        updatedAt: source.updatedAt.toISOString()
      }));

      return NextResponse.json(data);
    }
  } catch (error) {
    console.error("Error fetching sources:", error);
    return NextResponse.json(
      { error: "Failed to fetch sources" },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await getAuthenticatedSession(request);

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    const body = await request.json();
    const { sourceId } = body;

    if (!sourceId) {
      return NextResponse.json(
        { error: "sourceId is required" },
        { status: 400 }
      );
    }

    // Check if source exists
    const sourceExists = await db.select().from(sources).where(eq(sources.id, sourceId)).limit(1);

    if (sourceExists.length === 0) {
      return NextResponse.json(
        { error: "Source not found" },
        { status: 404 }
      );
    }

    // Check if user already owns this source
    const existing = await db
      .select()
      .from(userSources)
      .where(
        and(
          eq(userSources.userId, session.user.id),
          eq(userSources.sourceId, sourceId)
        )
      )
      .limit(1);

    if (existing.length > 0) {
      return NextResponse.json(
        { error: "Source already owned" },
        { status: 409 }
      );
    }

    // Add source to user's sources
    await db.insert(userSources).values({
      userId: session.user.id,
      sourceId
    });

    // Return updated list of owned sources
    const ownedSources = await db
      .select({ sourceId: userSources.sourceId })
      .from(userSources)
      .where(eq(userSources.userId, session.user.id));

    const ownedSourceIds = new Set(ownedSources.map((s) => s.sourceId));

    const allSources = await db.select().from(sources);
    const data: Source[] = allSources
      .filter((source) => ownedSourceIds.has(source.id))
      .map((source) => ({
        id: source.id,
        name: source.name,
        category: source.category,
        owned: true,
        updatedAt: source.updatedAt.toISOString()
      }));

    return NextResponse.json(data);
  } catch (error) {
    console.error("Error adding user source:", error);
    return NextResponse.json(
      { error: "Failed to add source" },
      { status: 500 }
    );
  }
}

