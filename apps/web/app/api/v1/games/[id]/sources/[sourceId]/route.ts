import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { games, gameMembers, gameSources } from "@/db/schema";
import { and, eq } from "drizzle-orm";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { fetchGameWithRelations } from "../../../_helpers";

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string; sourceId: string } }
) {
  try {
    const session = await getAuthenticatedSession(request);

    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
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

    const existing = await db
      .select({ sourceId: gameSources.sourceId })
      .from(gameSources)
      .where(
        and(
          eq(gameSources.gameId, params.id),
          eq(gameSources.sourceId, params.sourceId)
        )
      )
      .limit(1);

    if (existing.length === 0) {
      return NextResponse.json(
        { error: "Source not linked to this game" },
        { status: 404 }
      );
    }

    await db
      .delete(gameSources)
      .where(
        and(
          eq(gameSources.gameId, params.id),
          eq(gameSources.sourceId, params.sourceId)
        )
      );

    const updatedGame = await fetchGameWithRelations(params.id);
    if (!updatedGame) {
      return NextResponse.json(
        { error: "Failed to load updated game" },
        { status: 500 }
      );
    }

    return NextResponse.json(updatedGame);
  } catch (error) {
    console.error("Error removing game source:", error);
    return NextResponse.json(
      { error: "Failed to remove source from game" },
      { status: 500 }
    );
  }
}
