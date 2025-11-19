import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { characters, characterSources, sources } from "@/db/schema";
import { eq, and } from "drizzle-orm";
import type { Character } from "@ttrpg-center/types";

export async function GET(request: NextRequest) {
  try {
    const userId = request.nextUrl.searchParams.get("userId");
    const gameId = request.nextUrl.searchParams.get("gameId");

    // Build conditions first
    const conditions = [];
    if (userId && userId !== "all") {
      conditions.push(eq(characters.ownerId, userId));
    }
    if (gameId) {
      conditions.push(eq(characters.gameId, gameId));
    }

    // Build and execute query
    const query = db
      .select({
        id: characters.id,
        name: characters.name,
        className: characters.className,
        level: characters.level,
        ownerId: characters.ownerId,
        portraitUrl: characters.portraitUrl,
        createdAt: characters.createdAt,
        updatedAt: characters.updatedAt,
        system: characters.system,
        gameId: characters.gameId
      })
      .from(characters)
      .$dynamic();

    const data = await (conditions.length > 0
      ? query.where(and(...conditions))
      : query);

    // Get active source IDs for each character
    const charactersWithSources = await Promise.all(
      data.map(async (character) => {
        const activeSources = await db
          .select({ sourceId: characterSources.sourceId })
          .from(characterSources)
          .where(eq(characterSources.characterId, character.id));

        return {
          ...character,
          activeSourceIds: activeSources.map((s) => s.sourceId),
          createdAt: character.createdAt.toISOString(),
          updatedAt: character.updatedAt.toISOString()
        } as Character;
      })
    );

    return NextResponse.json(charactersWithSources);
  } catch (error) {
    console.error("Error fetching characters:", error);
    return NextResponse.json(
      { error: "Failed to fetch characters" },
      { status: 500 }
    );
  }
}

