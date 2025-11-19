import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { games, gameMembers } from "@/db/schema";
import { eq } from "drizzle-orm";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { fetchGameWithRelations } from "../_helpers";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  try {
    const game = await fetchGameWithRelations(params.id);
    if (!game) {
      return NextResponse.json({ error: "Game not found" }, { status: 404 });
    }
    return NextResponse.json(game);
  } catch (error) {
    console.error("Error fetching game:", error);
    return NextResponse.json(
      { error: "Failed to fetch game" },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const session = await getAuthenticatedSession(request);

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    const gameId = params.id;

    // Check if game exists and user is the GM
    const gameData = await db
      .select()
      .from(games)
      .where(eq(games.id, gameId))
      .limit(1);

    if (gameData.length === 0) {
      return NextResponse.json(
        { error: "Game not found" },
        { status: 404 }
      );
    }

    const game = gameData[0];

    // Only the GM can delete the game
    if (game.gmId !== session.user.id) {
      return NextResponse.json(
        { error: "Only the GM can delete this game" },
        { status: 403 }
      );
    }

    // Delete the game (cascades will handle members and sources)
    await db
      .delete(games)
      .where(eq(games.id, gameId));

    return NextResponse.json(
      { message: "Game deleted successfully" },
      { status: 200 }
    );
  } catch (error) {
    console.error("Error deleting game:", error);
    return NextResponse.json(
      { error: "Failed to delete game" },
      { status: 500 }
    );
  }
}

