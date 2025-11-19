import { NextRequest, NextResponse } from "next/server";
import type { User } from "@ttrpg-center/types";
import { db } from "@/lib/db";
import { authUsers, authUserRoles, authRoles } from "@/db/schema";
import { getAuthenticatedSession } from "@/lib/auth/server-session";
import { eq } from "drizzle-orm";

const unauthorized = NextResponse.json({ error: "Unauthorized" }, { status: 401 });
const forbidden = NextResponse.json({ error: "Forbidden" }, { status: 403 });

export async function GET(request: NextRequest) {
  const session = await getAuthenticatedSession(request);

  if (!session) {
    return unauthorized;
  }

  if (!session.roles.includes("admin")) {
    return forbidden;
  }

  const users = await db.select().from(authUsers).orderBy(authUsers.displayName);

  const roleRows = await db
    .select({ userId: authUserRoles.userId, role: authRoles.name })
    .from(authUserRoles)
    .innerJoin(authRoles, eq(authRoles.id, authUserRoles.roleId));

  const roleMap = new Map<string, Set<string>>();
  for (const row of roleRows) {
    const roles = roleMap.get(row.userId) ?? new Set<string>();
    roles.add(row.role);
    roleMap.set(row.userId, roles);
  }

  const payload: User[] = users.map((user) => ({
    id: user.id,
    displayName: user.displayName,
    email: user.email,
    avatarUrl: user.avatarUrl ?? undefined,
    roles: Array.from(roleMap.get(user.id) ?? new Set<string>()) as User["roles"]
  }));

  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "no-store"
    }
  });
}
