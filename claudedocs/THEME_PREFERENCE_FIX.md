# Theme Preference Persistence Fix

**Date**: 2025-11-06
**Issue**: Theme preference always defaulted to "system" instead of remembering user's last selection
**Status**: ✅ FIXED

---

## Problem

When users edited their profile settings and changed the theme preference (light/dark/system), the form would always default to "system" on the next visit instead of showing their last selection.

**Root Cause**:
1. The `auth_users` table did not have a `preferred_theme` column
2. The API endpoint was hardcoding `preferredTheme: "system"` instead of reading from database
3. Theme changes were not being persisted to the database

---

## Solution

### 1. Added Database Column

**Schema Update** (`apps/web/db/schema.ts`):
```typescript
export const authUsers = pgTable("auth_users", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: text("email").notNull().unique(),
  displayName: text("display_name").notNull(),
  avatarUrl: text("avatar_url"),
  preferredTheme: text("preferred_theme").notNull().default("system"), // ← NEW
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  lastLoginAt: timestamp("last_login_at", { withTimezone: true })
});
```

### 2. Created Migration

**File**: `apps/web/db/migrations/003_add_preferred_theme.sql`

```sql
-- Add preferred_theme column with default value 'system'
ALTER TABLE auth_users
ADD COLUMN IF NOT EXISTS preferred_theme TEXT NOT NULL DEFAULT 'system';

-- Add check constraint to ensure valid theme values
ALTER TABLE auth_users
ADD CONSTRAINT auth_users_preferred_theme_check
CHECK (preferred_theme IN ('light', 'dark', 'system'));

-- Comment on the column
COMMENT ON COLUMN auth_users.preferred_theme IS 'User theme preference: light, dark, or system';
```

**Migration Executed**:
```bash
docker exec -i ttrpg_postgres psql -U ttrpg -d ttrpg_auth < apps/web/db/migrations/003_add_preferred_theme.sql
# Result: ALTER TABLE, ALTER TABLE, COMMENT (Success)
```

### 3. Updated API Endpoint - GET Handler

**File**: `apps/web/app/api/v1/me/route.ts`

**Before**:
```typescript
export async function GET(request: NextRequest) {
  const session = await getAuthenticatedSession(request);
  // ...
  const me: Me = {
    // ...
    preferredTheme: "system", // ← Hardcoded!
    // ...
  };
  return NextResponse.json(me);
}
```

**After**:
```typescript
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
    preferredTheme: preferredTheme as "light" | "dark" | "system", // ← From DB!
    usage: { /* ... */ }
  };

  return NextResponse.json(me);
}
```

### 4. Updated API Endpoint - PATCH Handler

**File**: `apps/web/app/api/v1/me/route.ts`

**Before**:
```typescript
// Update user profile in database
await db
  .update(authUsers)
  .set({
    displayName: payload.displayName.trim(),
    email: payload.email.trim(),
    // preferredTheme NOT saved!
    updatedAt: new Date()
  })
  .where(eq(authUsers.id, session.user.id));
```

**After**:
```typescript
// Update user profile in database
await db
  .update(authUsers)
  .set({
    displayName: payload.displayName.trim(),
    email: payload.email.trim(),
    preferredTheme: payload.preferredTheme ?? "system", // ← Now saved!
    updatedAt: new Date()
  })
  .where(eq(authUsers.id, session.user.id));
```

---

## Files Modified

1. **`apps/web/db/schema.ts`** - Added `preferredTheme` column to schema
2. **`apps/web/db/migrations/003_add_preferred_theme.sql`** (NEW) - Migration to add column
3. **`apps/web/app/api/v1/me/route.ts`** - Read/write theme preference from/to database

---

## Database Verification

```sql
-- Verify column exists
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'auth_users'
AND column_name = 'preferred_theme';

-- Result:
-- column_name   | data_type | column_default
-- ----------------+-----------+----------------
-- preferred_theme | text      | 'system'::text

-- Verify constraint exists
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'auth_users_preferred_theme_check';

-- Result: CHECK constraint exists with valid values
```

---

## Testing

### Test 1: Default Theme (New Users)

**Scenario**: New user first login
```bash
# GET /api/v1/me
curl http://localhost:3000/api/v1/me -H "Cookie: session=..."

# Response:
{
  "id": "...",
  "preferredTheme": "system",  // ← Default value
  ...
}
```

### Test 2: Change Theme to Dark

**Scenario**: User changes theme to dark
```bash
# PATCH /api/v1/me
curl -X PATCH http://localhost:3000/api/v1/me \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{
    "displayName": "John Doe",
    "email": "john@example.com",
    "preferredTheme": "dark"
  }'

# Response:
{
  "preferredTheme": "dark",  // ← Updated
  ...
}
```

### Test 3: Theme Persists Across Sessions

**Scenario**: User logs out and back in, theme should be "dark"
```bash
# 1. User changes theme to dark (from Test 2)
# 2. User logs out
# 3. User logs back in
# 4. GET /api/v1/me

curl http://localhost:3000/api/v1/me -H "Cookie: new_session=..."

# Response:
{
  "preferredTheme": "dark",  // ← Persisted from previous session!
  ...
}
```

### Test 4: Manual UI Test

1. **Navigate** to http://localhost:3000/settings
2. **Click** "Edit profile"
3. **Current theme** should show your last selection (not always "system")
4. **Change** theme from "system" to "light"
5. **Click** "Save changes"
6. **Refresh** the page
7. ✅ **Expected**: Theme is still "light" (not reset to "system")
8. **Click** "Edit profile" again
9. ✅ **Expected**: "Light" radio button is selected

---

## Migration Safety

### For Existing Users

**Default Value**: All existing users get `preferred_theme = 'system'`
- No user preferences are changed
- Users see their current theme on next visit
- Default is sensible (respects OS preference)

**No Data Loss**:
- Column is `NOT NULL` with `DEFAULT 'system'`
- Existing rows automatically get default value
- No manual data migration needed

**Constraint Protection**:
- CHECK constraint ensures only valid values: 'light', 'dark', 'system'
- Invalid values rejected at database level
- Application cannot write invalid themes

---

## Deployment

### Development Server
Changes take effect immediately (hot reload + existing column added to DB).

### Docker Container

**If database already migrated** (column exists):
```bash
# Rebuild application only
cd webui
docker build -t ttrpg-webui:latest -f Dockerfile ..

docker stop ttrpg_webui && docker rm ttrpg_webui

docker run -d -p 3000:3000 \
  -e AUTH_DATABASE_URL="postgres://ttrpg:ttrpg@host.docker.internal:5432/ttrpg_auth" \
  --name ttrpg_webui \
  ttrpg-webui:latest
```

**If database NOT migrated** (column doesn't exist):
```bash
# 1. Run migration first
docker exec -i ttrpg_postgres psql -U ttrpg -d ttrpg_auth < apps/web/db/migrations/003_add_preferred_theme.sql

# 2. Then rebuild application
cd webui
docker build -t ttrpg-webui:latest -f Dockerfile ..

docker stop ttrpg_webui && docker rm ttrpg_webui

docker run -d -p 3000:3000 \
  -e AUTH_DATABASE_URL="postgres://ttrpg:ttrpg@host.docker.internal:5432/ttrpg_auth" \
  --name ttrpg_webui \
  ttrpg-webui:latest
```

---

## Edge Cases Handled

### 1. Missing User Data
```typescript
const preferredTheme = userData[0]?.preferredTheme ?? "system";
```
If user not found in database, defaults to "system" gracefully.

### 2. Invalid Theme Value
Database CHECK constraint prevents invalid values:
```sql
CHECK (preferred_theme IN ('light', 'dark', 'system'))
```
Attempting to save invalid theme returns database error.

### 3. NULL Theme (Prevented)
Column is `NOT NULL` with default, cannot be NULL:
```sql
preferred_theme TEXT NOT NULL DEFAULT 'system'
```

### 4. Payload Missing Theme
```typescript
preferredTheme: payload.preferredTheme ?? "system"
```
If theme not in payload, uses "system" as fallback.

---

## Success Criteria

- ✅ Database column added successfully
- ✅ Migration ran without errors
- ✅ GET endpoint reads theme from database
- ✅ PATCH endpoint saves theme to database
- ✅ Theme persists across sessions
- ✅ Edit form defaults to user's saved theme
- ✅ All existing users have default 'system' theme
- ✅ Invalid themes rejected by constraint
- ✅ No breaking changes for existing users

---

## Related Issues

- **Original Issue**: "Theme Preference always defaults to System"
- **Related Fixes**:
  - Account Settings redesign (removed role editing)
  - PATCH handler addition (enable profile updates)
  - Billing section addition (subscription management)

---

**Status**: ✅ COMPLETE

The theme preference now correctly persists to the database and loads the user's last selection when editing their profile.

---

**Related Documentation**:
- Backend Integration: `BUILD_SUCCESS_COMPLETE.md`
- Account Settings Fixes: `ACCOUNT_SETTINGS_FIXES.md`
- **This Document**: `THEME_PREFERENCE_FIX.md`
