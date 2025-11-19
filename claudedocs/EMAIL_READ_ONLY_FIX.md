# Email Read-Only Fix

**Date**: 2025-11-06
**Issue**: Email field should be displayed but not editable in profile settings
**Status**: ✅ FIXED

---

## Problem

In the Account Settings Edit profile form, the email field was fully editable, which could cause issues:
- Email changes could break OAuth authentication links
- Email is used as the unique identifier for user accounts
- Users shouldn't be able to change their authentication email

**User Request**: "Email should not be editable however it should still be displayed."

---

## Solution

Modified the Edit profile form to display email as read-only text instead of an editable input field.

### Changes Made

**File**: `apps/web/components/home\user-profile-panel.tsx`

#### 1. Updated Form Description (Line 91)

**Before**:
```typescript
<p className="text-sm text-slate-500 dark:text-slate-400">
  Update your display name, email, and theme preference.
</p>
```

**After**:
```typescript
<p className="text-sm text-slate-500 dark:text-slate-400">
  Update your display name and theme preference.
</p>
```

#### 2. Replaced Email Input with Read-Only Display (Lines 150-160)

**Before** (Editable Input):
```typescript
<label className="space-y-1">
  <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
    Email
  </span>
  <input
    type="email"
    value={formState.email}
    onChange={(event) =>
      setFormState((prev) => prev && { ...prev, email: event.target.value })
    }
    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
  />
</label>
```

**After** (Read-Only Display):
```typescript
<div className="space-y-1">
  <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
    Email
  </span>
  <div className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
    {session.email}
  </div>
  <p className="text-xs text-slate-400 dark:text-slate-500">
    Email cannot be changed
  </p>
</div>
```

**Key Differences**:
- Changed from `<label>` + `<input>` to `<div>` + `<div>` (no input element)
- Displays `session.email` directly (not from formState)
- Background color changed to `bg-slate-50` / `bg-slate-800` (visual indicator it's read-only)
- Text color muted to `text-slate-500` / `text-slate-400` (indicates non-editable)
- Added helper text "Email cannot be changed" for clarity

#### 3. Updated Form Submission Handler (Line 50)

**Before**:
```typescript
const payload = {
  displayName: formState.displayName.trim(),
  email: formState.email.trim(), // ← User could edit this
  preferredTheme: formState.preferredTheme
};

// Email validation
if (!payload.email || !payload.email.includes("@")) {
  throw new Error("A valid email address is required.");
}
```

**After**:
```typescript
const payload = {
  displayName: formState.displayName.trim(),
  email: session.email, // ← Always use session email (read-only, not editable)
  preferredTheme: formState.preferredTheme
};

// No email validation needed (using session value, always valid)
```

**Key Changes**:
- Always sends `session.email` instead of `formState.email`
- Removed email validation (unnecessary since email doesn't change)
- Added comment explaining read-only behavior

---

## UI Behavior

### View Mode (Not Editing)
The email is displayed as read-only text (no change from before):
```
Display name: John Doe
Email: john@example.com
Theme: Dark
Roles: Player, GM
```

### Edit Mode (After Fix)
```
┌─ Display name ────────────────────┐
│ [John Doe                       ] │ ← Editable
└───────────────────────────────────┘

┌─ Email ───────────────────────────┐
│  john@example.com                 │ ← Read-only (grayed out)
│  Email cannot be changed          │
└───────────────────────────────────┘

Theme preference: ◉ Light  ○ Dark  ○ System
```

**Visual Indicators for Read-Only**:
- Grayed background (`bg-slate-50` in light, `bg-slate-800` in dark)
- Muted text color (`text-slate-500` in light, `text-slate-400` in dark)
- Helper text below: "Email cannot be changed"
- No input focus ring or hover effects

---

## Testing

### Test 1: Email Display in View Mode

**Scenario**: User views their profile without editing

```
1. Navigate to /settings
2. View profile section
3. ✅ Expected: Email is displayed clearly
```

### Test 2: Email Display in Edit Mode

**Scenario**: User clicks "Edit profile"

```
1. Navigate to /settings
2. Click "Edit profile" button
3. ✅ Expected: Email shown in read-only field (grayed out)
4. ✅ Expected: Helper text "Email cannot be changed" visible
5. ✅ Expected: No cursor or focus when clicking email field
```

### Test 3: Form Submission Without Email Change

**Scenario**: User updates display name, email stays the same

```
1. Navigate to /settings → Edit profile
2. Change display name to "NewName"
3. Note: Email field cannot be edited
4. Click "Save changes"
5. ✅ Expected: Display name updated successfully
6. ✅ Expected: Email remains unchanged (as intended)
```

### Test 4: Verify Backend Receives Correct Email

**Scenario**: Ensure session email (not formState) is sent to API

```
1. User with email "test@example.com" edits profile
2. Backend receives PATCH /api/v1/me with:
   {
     "displayName": "New Name",
     "email": "test@example.com",  // ← From session, not form input
     "preferredTheme": "dark"
   }
3. ✅ Expected: Email matches user's session email exactly
```

---

## Why Email Should Be Read-Only

### Security Reasons
1. **OAuth Account Linking**: Email is used to match OAuth accounts (Google, etc.) to user records. Changing email could break authentication.
2. **Unique Identifier**: Email is the unique key for user accounts. Changing it could create conflicts or orphan data.
3. **Session Integrity**: Changing email mid-session could invalidate the session or cause authentication errors.

### User Experience
1. **Clarity**: Users understand they can't change their login email (tied to OAuth provider)
2. **Prevents Mistakes**: Users can't accidentally change their email and lock themselves out
3. **Consistency**: Email changes should be handled through OAuth provider (e.g., change Google account email, not here)

---

## Edge Cases Handled

### 1. User Tries to Modify Email in Browser DevTools
Even if user modifies formState via browser console:
```javascript
// Malicious attempt to change email
formState.email = "hacker@evil.com"
```
**Result**: Form submission uses `session.email`, not `formState.email` ✅

### 2. Email Field in FormState
Email is still in formState (line 31: `email: session.email`) but:
- Not used in form submission (uses `session.email` directly)
- Not editable in UI
- Keeps form state consistent for display purposes

### 3. Session Email Changes (Edge Case)
If user's session email somehow changes during edit:
- Form uses latest `session.email` (not stale formState value)
- Ensures consistency with authentication system
- Prevents desync between form and session

---

## Alternative Approaches Considered

### Approach 1: Remove Email from Edit Form Entirely
**Pros**: Simplest, no ambiguity
**Cons**: Users can't see their email in edit mode (bad UX)
**Decision**: Rejected - email should be visible

### Approach 2: Make Email Input Disabled
```typescript
<input type="email" value={session.email} disabled />
```
**Pros**: Still an input element, standard HTML pattern
**Cons**: Disabled inputs look less polished, not clear it's intentionally read-only
**Decision**: Rejected - custom read-only display looks better

### Approach 3: Show Email with Copy Button
**Pros**: User can easily copy email
**Cons**: Adds complexity, not requested
**Decision**: Rejected - YAGNI (may add later if requested)

### ✅ Chosen Approach: Custom Read-Only Display
**Pros**:
- Clear visual distinction from editable fields
- Explicit helper text ("Email cannot be changed")
- Consistent with existing read-only displays (roles)
**Cons**:
- More CSS classes to maintain
**Decision**: Accepted - best UX for this use case

---

## Related Files

**Modified**:
- `apps/web/components/home/user-profile-panel.tsx` - Email field made read-only

**Related Components**:
- `apps/web/app/api/v1/me/route.ts` - PATCH handler (doesn't update email from payload)
- `apps/web/lib/auth/repository.ts` - OAuth doesn't overwrite email (already unique key)

---

## Success Criteria

- ✅ Email displayed in view mode
- ✅ Email displayed (read-only) in edit mode
- ✅ Email visually distinct from editable fields
- ✅ Helper text clearly indicates email is not editable
- ✅ Form submission uses session email (not form input)
- ✅ No validation errors for email (always valid)
- ✅ Users can still update display name and theme
- ✅ No breaking changes to existing functionality

---

**Status**: ✅ COMPLETE

Email is now displayed as read-only in the Edit profile form, preventing accidental changes while keeping it visible for user reference.

---

**Related Documentation**:
- Account Settings Redesign: `ACCOUNT_SETTINGS_FIXES.md`
- OAuth Display Name Fix: `OAUTH_DISPLAY_NAME_FIX.md`
- Theme Preference Fix: `THEME_PREFERENCE_FIX.md`
- **This Document**: `EMAIL_READ_ONLY_FIX.md`
