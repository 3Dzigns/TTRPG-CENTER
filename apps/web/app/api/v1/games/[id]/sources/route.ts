import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { games, gameMembers, gameSources, sources as sourcesTable } from "@/db/schema";
import { and, eq, sql } from "drizzle-orm";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { fetchGameWithRelations, getGameSourceLimit } from "../../_helpers";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const session = await getAuthenticatedSession(request);

    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await request.json().catch(() => null);
    const sourceId = body?.sourceId as string | undefined;

    if (!sourceId) {
      return NextResponse.json(
        { error: "sourceId is required" },
        { status: 400 }
      );
    }

    const gameRows = await db
      .select()
      .from(games)
      .where(eq(games.id, params.id))
      .limit(1);

    if (gameRows.length === 0) {
      return NextResponse.json({ error: "Game not found" }, { status: 404 });
    }

    const game = gameRows[0];
    const membershipRows = await db
      .select({ role: gameMembers.role })
      .from(gameMembers)
      .where(
        and(
          eq(gameMembers.gameId, params.id),
          eq(gameMembers.userId, session.user.id)
        )
      )
      .limit(1);

    const membership = membershipRows[0];
    const isAdmin = session.roles.includes("admin");
    const canManage =
      isAdmin ||
      game.gmId === session.user.id ||
      membership?.role === "gm" ||
      membership?.role === "co-gm";

    if (!canManage) {
      return NextResponse.json(
        { error: "Only GMs or co-GMs can manage sources" },
        { status: 403 }
      );
    }

    const sourceRecord = await db.query.sources.findFirst({
      where: eq(sourcesTable.id, sourceId)
    });

    if (!sourceRecord) {
      return NextResponse.json({ error: "Source not found" }, { status: 404 });
    }

    const existing = await db
      .select({ sourceId: gameSources.sourceId })
      .from(gameSources)
      .where(
        and(
          eq(gameSources.gameId, params.id),
          eq(gameSources.sourceId, sourceId)
        )
      )
      .limit(1);

    if (existing.length > 0) {
      return NextResponse.json(
        { error: "Source already added to this game" },
        { status: 409 }
      );
    }

    const [{ count }] = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(gameSources)
      .where(eq(gameSources.gameId, params.id));

    const sourceLimit = await getGameSourceLimit(game);

    if (count >= sourceLimit) {
      return NextResponse.json(
        { error: "Source limit reached for this game" },
        { status: 409 }
      );
    }

    await db.insert(gameSources).values({
      gameId: params.id,
      sourceId
    });

    const updatedGame = await fetchGameWithRelations(params.id);
    if (!updatedGame) {
      return NextResponse.json(
        { error: "Failed to load updated game" },
        { status: 500 }
      );
    }

    return NextResponse.json(updatedGame);
  } catch (error) {
    console.error("Error adding game source:", error);
    return NextResponse.json(
      { error: "Failed to add source to game" },
      { status: 500 }
    );
  }
}
