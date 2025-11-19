import { NextRequest, NextResponse } from "next/server";
import type { Me, UserProfileUpdateInput } from "@ttrpg-center/types";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { db } from "@/lib/db";
import { authUsers } from "@/db/schema";
import { eq } from "drizzle-orm";

const unauthorized = NextResponse.json(
  { error: "Unauthorized" },
  {
    status: 401,
    headers: {
      "Cache-Control": "no-store"
    }
  }
);

export async function GET(request: NextRequest) {
  const session = await getAuthenticatedSession(request);

  if (!session) {
    return unauthorized;
  }

  // Get user's preferred theme from database
  const userData = await db
    .select({ preferredTheme: authUsers.preferredTheme })
    .from(authUsers)
    .where(eq(authUsers.id, session.user.id))
    .limit(1);

  const preferredTheme = userData[0]?.preferredTheme ?? "system";

  const me: Me = {
    id: session.user.id,
    displayName: session.user.displayName,
    email: session.user.email,
    roles: session.roles,
    avatarUrl: session.user.avatarUrl ?? undefined,
    preferredTheme: preferredTheme as "light" | "dark" | "system",
    usage: {
      totalSecondsPlayed: 0,
      monthlySessionCount: 0,
      automationCreditsRemaining: 0,
      textAssistRemaining: 0,
      audioBridgeRemaining: 0,
      discordBridgeRemaining: 0
    }
  };

  return NextResponse.json(me, {
    headers: {
      "Cache-Control": "no-store"
    }
  });
}

export async function PATCH(request: NextRequest) {
  const session = await getAuthenticatedSession(request);

  if (!session) {
    return unauthorized;
  }

  try {
    const body = await request.json();
    const payload: UserProfileUpdateInput = body;

    // Validate input
    if (!payload.displayName || payload.displayName.trim() === "") {
      return NextResponse.json(
        { error: "Display name is required" },
        { status: 400 }
      );
    }

    if (!payload.email || !payload.email.includes("@")) {
      return NextResponse.json(
        { error: "Valid email is required" },
        { status: 400 }
      );
    }

    // Update user profile in database
    await db
      .update(authUsers)
      .set({
        displayName: payload.displayName.trim(),
        email: payload.email.trim(),
        preferredTheme: payload.preferredTheme ?? "system",
        updatedAt: new Date()
      })
      .where(eq(authUsers.id, session.user.id));

    // Return updated profile
    const me: Me = {
      id: session.user.id,
      displayName: payload.displayName.trim(),
      email: payload.email.trim(),
      roles: session.roles,
      avatarUrl: session.user.avatarUrl ?? undefined,
      preferredTheme: payload.preferredTheme ?? "system",
      usage: {
        totalSecondsPlayed: 0,
        monthlySessionCount: 0,
        automationCreditsRemaining: 0,
        textAssistRemaining: 0,
        audioBridgeRemaining: 0,
        discordBridgeRemaining: 0
      }
    };

    return NextResponse.json(me, {
      headers: {
        "Cache-Control": "no-store"
      }
    });
  } catch (error) {
    console.error("Error updating profile:", error);
    return NextResponse.json(
      { error: "Failed to update profile" },
      { status: 500 }
    );
  }
}
