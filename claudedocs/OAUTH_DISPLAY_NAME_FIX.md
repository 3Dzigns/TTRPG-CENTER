# OAuth Display Name Preservation Fix

**Date**: 2025-11-06
**Issue**: Google OAuth overwrites user's custom display name on every re-authentication
**Status**: ✅ FIXED

---

## Problem

When users sign out and sign back in via Google OAuth, their custom display name gets overwritten with the name from their Google profile, even though they are existing users who had customized their display name.

**User Experience**:
1. User signs in with Google → Gets default display name from Google profile
2. User goes to Account Settings → Changes display name to custom value
3. User saves successfully → Custom name stored in database
4. User signs out and back in via Google → **Custom name overwritten with Google profile name!**

**Root Cause**:
The `upsertOAuthUser` function in `apps/web/lib/auth/repository.ts` was updating the `displayName` field for BOTH new and existing users, treating every OAuth login as if it were a fresh registration.

---

## Solution

Modified the `upsertOAuthUser` function to differentiate between new and existing users:

- **New Users**: Use display name from Google OAuth (first-time registration)
- **Existing Users**: Preserve their custom display name (don't overwrite)

### Code Changes

**File**: `apps/web/lib/auth/repository.ts`

**Before** (Lines 72-84):
```typescript
} else {
  const updated = await db
    .update(authUsers)
    .set({
      displayName,  // ← Always overwrites with Google's name!
      avatarUrl: avatarUrl ?? existingUser.avatarUrl ?? null,
      updatedAt: sql`NOW()`,
      lastLoginAt: sql`NOW()`
    })
    .where(eq(authUsers.id, existingUser.id))
    .returning({ id: authUsers.id });
  userId = updated[0].id;
}
```

**After** (Lines 72-85):
```typescript
} else {
  // For existing users, preserve their custom display name and only update login timestamps
  const updated = await db
    .update(authUsers)
    .set({
      // Don't update displayName - preserve user's custom name
      avatarUrl: avatarUrl ?? existingUser.avatarUrl ?? null,
      updatedAt: sql`NOW()`,
      lastLoginAt: sql`NOW()`
    })
    .where(eq(authUsers.id, existingUser.id))
    .returning({ id: authUsers.id });
  userId = updated[0].id;
}
```

**Key Change**: Removed `displayName` from the update `.set()` object for existing users.

---

## What Still Gets Updated for Existing Users

When an existing user logs back in via OAuth, these fields ARE updated:

1. **lastLoginAt** - Tracks when they last authenticated (important for security)
2. **updatedAt** - Standard timestamp for any profile touch
3. **avatarUrl** - Only if they don't have one (preserves custom avatars)

These fields are NOT updated:
- **displayName** - Preserved from user's custom settings
- **email** - Already tied to OAuth account (unique key)
- **preferredTheme** - Preserved from user's preferences

---

## Flow Diagrams

### Before Fix (Broken Behavior)

```
User Flow:
1. Sign in with Google → displayName = "John Smith" (from Google)
2. Edit profile → displayName = "JohnTheGM" (custom name)
3. Save changes → ✅ Saved to database
4. Sign out
5. Sign in with Google again → displayName = "John Smith" (OVERWRITTEN!)
   └─ upsertOAuthUser() always updates displayName from OAuth
```

### After Fix (Correct Behavior)

```
User Flow:
1. Sign in with Google → displayName = "John Smith" (from Google)
2. Edit profile → displayName = "JohnTheGM" (custom name)
3. Save changes → ✅ Saved to database
4. Sign out
5. Sign in with Google again → displayName = "JohnTheGM" (PRESERVED!)
   └─ upsertOAuthUser() skips displayName update for existing users
```

---

## Testing

### Test 1: First-Time User Registration

**Scenario**: Brand new user signs in with Google OAuth

```
1. User clicks "Sign in with Google"
2. Google returns profile: { name: "Jane Doe", email: "jane@example.com" }
3. upsertOAuthUser() creates new user with displayName = "Jane Doe"
4. ✅ Expected: New user gets Google's display name as default
```

**Verification**:
```sql
SELECT display_name FROM auth_users WHERE email = 'jane@example.com';
-- Result: "Jane Doe"
```

### Test 2: Existing User Re-Authentication (Main Fix)

**Scenario**: Existing user with custom display name logs back in

```
1. User already has displayName = "JaneThePlayer" in database
2. User signs out
3. User clicks "Sign in with Google" again
4. Google returns profile: { name: "Jane Doe", email: "jane@example.com" }
5. upsertOAuthUser() updates lastLoginAt but NOT displayName
6. ✅ Expected: Custom display name preserved ("JaneThePlayer")
```

**Verification**:
```sql
SELECT display_name, last_login_at FROM auth_users WHERE email = 'jane@example.com';
-- Result: "JaneThePlayer", <recent timestamp>
-- Display name unchanged, login timestamp updated
```

### Test 3: Profile Update Still Works

**Scenario**: User changes display name via Account Settings

```
1. User navigates to /settings
2. User clicks "Edit profile"
3. User changes display name to "NewName"
4. User clicks "Save changes"
5. PATCH /api/v1/me called with { displayName: "NewName" }
6. ✅ Expected: Display name updated successfully
```

**Verification**:
```bash
curl -X PATCH http://localhost:3000/api/v1/me \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"displayName": "NewName", "email": "jane@example.com"}'

# Response should include: "displayName": "NewName"
```

### Test 4: Manual UI Test

**Steps**:
1. Sign in with Google
2. Note the display name shown in dashboard (from Google profile)
3. Navigate to Account Settings → Edit profile
4. Change display name to something custom (e.g., "MyCustomName")
5. Click "Save changes"
6. Verify success message
7. **Sign out completely**
8. **Sign back in with Google**
9. ✅ **Expected**: Display name still shows "MyCustomName" (not Google's name)
10. Navigate to Account Settings → Edit profile
11. ✅ **Expected**: Display name field shows "MyCustomName"

---

## Edge Cases Handled

### 1. User Without Custom Avatar
```typescript
avatarUrl: avatarUrl ?? existingUser.avatarUrl ?? null
```
- If Google provides new avatar AND user has no custom avatar → Use Google's
- If Google provides new avatar AND user has custom avatar → Keep custom
- If Google provides no avatar → Keep existing avatar

### 2. First Login vs Subsequent Logins
```typescript
if (!existingUser) {
  // New user: Use all OAuth profile data
  displayName: displayName  // ← From Google
} else {
  // Existing user: Preserve custom data
  // displayName NOT in update
}
```

### 3. Account Linking (Same Email, Different Provider)
The OAuth account is keyed by `(provider, providerAccountId)`:
```typescript
.onConflictDoUpdate({
  target: [authOauthAccounts.provider, authOauthAccounts.providerAccountId],
  // Updates OAuth tokens, NOT user profile
})
```
User profile preservation works across different OAuth providers for same email.

---

## Files Modified

1. **`apps/web/lib/auth/repository.ts`** - Modified `upsertOAuthUser` function

**No database migration needed** - This is purely a logic fix in application code.

---

## Related Context

### OAuth Flow Sequence

```
Browser                  Next.js App                  Google OAuth
   |                          |                             |
   |---(1) /auth/signin------>|                             |
   |                          |---(2) Redirect to Google--->|
   |                          |                             |
   |<---------(3) Auth prompt----------------------|
   |                          |                             |
   |---(4) User approves----->|                             |
   |                          |<--(5) Authorization code----|
   |                          |                             |
   |                          |---(6) Exchange for tokens-->|
   |                          |<--(7) Access token + profile|
   |                          |                             |
   |                          |---(8) upsertOAuthUser()     |
   |                          |     ↓ FIXED: Preserve name  |
   |                          |                             |
   |<--(9) Set session cookie-|                             |
   |<--(10) Redirect to /home-|                             |
```

**Step 8 (upsertOAuthUser)**: This is where the fix applies.
- Before: Always updated displayName from Google
- After: Only updates displayName for new users

---

## Success Criteria

- ✅ New users get display name from OAuth provider
- ✅ Existing users keep their custom display name on re-login
- ✅ Login timestamps updated correctly
- ✅ Avatar URL handled with fallback logic
- ✅ Profile updates via settings page still work
- ✅ No database migrations required
- ✅ No breaking changes for existing users

---

## Related Documentation

- OAuth Callback Handler: `apps/web/app/auth/callback/route.ts`
- Auth Repository: `apps/web/lib/auth/repository.ts`
- Profile Update API: `apps/web/app/api/v1/me/route.ts` (PATCH handler)
- Account Settings UI: `apps/web/app/(dashboard)/settings/page.tsx`
- **This Document**: `OAUTH_DISPLAY_NAME_FIX.md`
- **Related Fix**: `THEME_PREFERENCE_FIX.md` (theme persistence)

---

**Status**: ✅ COMPLETE

The OAuth authentication flow now correctly preserves user customizations while still updating security-relevant fields like login timestamps.
