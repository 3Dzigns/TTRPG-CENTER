import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { games, gameMembers } from "@/db/schema";
import { eq, or } from "drizzle-orm";
import type { GameCreateInput } from "@ttrpg-center/types";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { randomBytes } from "crypto";
import { hydrateGame } from "./_helpers";

// Generate a URL-safe random string for invite codes
function generateInviteCode(length = 10): string {
  return randomBytes(length)
    .toString("base64")
    .replace(/[+/=]/g, "")
    .slice(0, length);
}

export async function GET(request: NextRequest) {
  try {
    const userId = request.nextUrl.searchParams.get("userId");

    // Build base query
    const baseQuery = db.select().from(games);

    let gamesData;

    if (userId && userId !== "all") {
      // Filter games where user is GM or a member
      const userGames = await db
        .select({ gameId: gameMembers.gameId })
        .from(gameMembers)
        .where(eq(gameMembers.userId, userId));

      const gameIds = userGames.map((g) => g.gameId);

      if (gameIds.length === 0) {
        return NextResponse.json([]);
      }

      gamesData = await baseQuery.where(
        or(
          eq(games.gmId, userId),
          ...gameIds.map((id) => eq(games.id, id))
        )
      );
    } else {
      gamesData = await baseQuery;
    }

    const enrichedGames = await Promise.all(gamesData.map((game) => hydrateGame(game)));
    return NextResponse.json(enrichedGames);
  } catch (error) {
    console.error("Error fetching games:", error);
    return NextResponse.json(
      { error: "Failed to fetch games" },
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

    const body: GameCreateInput = await request.json();
    const { title, summary, tier = "standard" } = body;

    if (!title || title.trim().length === 0) {
      return NextResponse.json(
        { error: "Game title is required" },
        { status: 400 }
      );
    }

    // Generate unique invite code
    const inviteCode = generateInviteCode(10);

    // Create the game (let database generate UUID for id)
    const [newGame] = await db
      .insert(games)
      .values({
        title: title.trim(),
        summary: summary?.trim() || null,
        tier: tier,
        status: "active",
        gmId: session.user.id,
        inviteCode,
        sessionCount: 0,
        allowAudioBridge: false,
        allowSummaries: false,
        allowDiscordBridge: false
      })
      .returning();

    // Add GM as a member
    await db.insert(gameMembers).values({
      gameId: newGame.id,
      userId: session.user.id,
      role: "gm",
      status: "active",
      joinedAt: new Date()
    });

    const enrichedGame = await hydrateGame(newGame);
    return NextResponse.json(enrichedGame, { status: 201 });
  } catch (error) {
    console.error("Error creating game:", error);
    return NextResponse.json(
      { error: "Failed to create game" },
      { status: 500 }
    );
  }
}
