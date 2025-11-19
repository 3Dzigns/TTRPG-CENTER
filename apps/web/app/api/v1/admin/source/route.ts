import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { sources } from "@/db/schema";
import { eq } from "drizzle-orm";
import { randomUUID } from "crypto";
import type {
  AdminSourceMutationRequest,
  AdminSourceMutationResult,
  SourceCategory
} from "@ttrpg-center/types";
import { getAuthenticatedSession } from "@/lib/auth/server-session";

export async function POST(request: NextRequest) {
  try {
    const session = await getAuthenticatedSession(request);

    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    // Check if user is admin (you may have a different admin check)
    // For now, we'll check if email is admin@example.com
    if (session.user.email !== "admin@example.com") {
      return NextResponse.json(
        { error: "Forbidden - Admin access required" },
        { status: 403 }
      );
    }

    const body: AdminSourceMutationRequest = await request.json();
    const { action, source: sourceData } = body;

    if (!action || !sourceData) {
      return NextResponse.json(
        { error: "action and source are required" },
        { status: 400 }
      );
    }

    let result: AdminSourceMutationResult;

    switch (action) {
      case "create": {
        if (!sourceData.name || !sourceData.category) {
          return NextResponse.json(
            { error: "name and category are required for creation" },
            { status: 400 }
          );
        }

        // Check if source with same name exists
        const existing = await db
          .select()
          .from(sources)
          .where(eq(sources.name, sourceData.name))
          .limit(1);

        if (existing.length > 0) {
          return NextResponse.json(
            { error: "A source with this name already exists" },
            { status: 409 }
          );
        }

        // Create new source
        const [newSource] = await db
          .insert(sources)
          .values({
            name: sourceData.name,
            category: sourceData.category as SourceCategory
          })
          .returning();

        result = {
          traceId: randomUUID(),
          action: "create",
          source: {
            id: newSource.id,
            name: newSource.name,
            category: newSource.category,
            owned: sourceData.owned ?? false,
            updatedAt: newSource.updatedAt.toISOString()
          }
        };
        break;
      }

      case "update": {
        if (!sourceData.id) {
          return NextResponse.json(
            { error: "source id is required for update" },
            { status: 400 }
          );
        }

        // Check if source exists
        const existingSource = await db
          .select()
          .from(sources)
          .where(eq(sources.id, sourceData.id))
          .limit(1);

        if (existingSource.length === 0) {
          return NextResponse.json(
            { error: "Source not found" },
            { status: 404 }
          );
        }

        // Update source
        const [updatedSource] = await db
          .update(sources)
          .set({
            name: sourceData.name,
            category: sourceData.category as SourceCategory,
            updatedAt: new Date()
          })
          .where(eq(sources.id, sourceData.id))
          .returning();

        result = {
          traceId: randomUUID(),
          action: "update",
          source: {
            id: updatedSource.id,
            name: updatedSource.name,
            category: updatedSource.category,
            owned: sourceData.owned ?? false,
            updatedAt: updatedSource.updatedAt.toISOString()
          }
        };
        break;
      }

      case "delete": {
        if (!sourceData.id) {
          return NextResponse.json(
            { error: "source id is required for deletion" },
            { status: 400 }
          );
        }

        // Check if source exists
        const existingSource = await db
          .select()
          .from(sources)
          .where(eq(sources.id, sourceData.id))
          .limit(1);

        if (existingSource.length === 0) {
          return NextResponse.json(
            { error: "Source not found" },
            { status: 404 }
          );
        }

        // Delete source
        await db.delete(sources).where(eq(sources.id, sourceData.id));

        result = {
          traceId: randomUUID(),
          action: "delete",
          source: {
            id: existingSource[0].id,
            name: existingSource[0].name,
            category: existingSource[0].category,
            owned: sourceData.owned ?? false,
            updatedAt: existingSource[0].updatedAt.toISOString()
          }
        };
        break;
      }

      default:
        return NextResponse.json(
          { error: `Unknown action: ${action}` },
          { status: 400 }
        );
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in admin source mutation:", error);
    return NextResponse.json(
      { error: "Failed to process source mutation" },
      { status: 500 }
    );
  }
}
