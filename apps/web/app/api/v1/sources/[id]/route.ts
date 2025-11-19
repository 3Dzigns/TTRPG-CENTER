import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { sources, userSources } from "@/db/schema";
import { and, eq } from "drizzle-orm";
import type { Source } from "@ttrpg-center/types";
import { getAuthenticatedSession } from "@/lib/auth/server-session";

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

    const sourceId = params.id;

    // Check if source exists
    const sourceExists = await db
      .select()
      .from(sources)
      .where(eq(sources.id, sourceId))
      .limit(1);

    if (sourceExists.length === 0) {
      return NextResponse.json(
        { error: "Source not found" },
        { status: 404 }
      );
    }

    // Check if user owns this source
    const userSource = await db
      .select()
      .from(userSources)
      .where(
        and(
          eq(userSources.userId, session.user.id),
          eq(userSources.sourceId, sourceId)
        )
      )
      .limit(1);

    if (userSource.length === 0) {
      return NextResponse.json(
        { error: "You do not own this source" },
        { status: 403 }
      );
    }

    // Remove the user-source association
    await db
      .delete(userSources)
      .where(
        and(
          eq(userSources.userId, session.user.id),
          eq(userSources.sourceId, sourceId)
        )
      );

    // Return updated list of owned sources
    const remainingOwnedSources = await db
      .select({ sourceId: userSources.sourceId })
      .from(userSources)
      .where(eq(userSources.userId, session.user.id));

    const ownedSourceIds = new Set(remainingOwnedSources.map((s) => s.sourceId));

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
    console.error("Error removing user source:", error);
    return NextResponse.json(
      { error: "Failed to remove source" },
      { status: 500 }
    );
  }
}
