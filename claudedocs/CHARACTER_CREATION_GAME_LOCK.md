# Character Creation Game Lock Feature

**Date**: 2025-11-06
**Feature**: Lock "New Character" button until player joins a game
**Status**: ✅ IMPLEMENTED

---

## Problem

Users could create characters without being linked to any games, which creates orphaned characters with no game context.

**User Request**: "New Character on the Player Hub Pages needs to be locked unless the player is linked to a game."

---

## Solution

Modified the CharacterList component to support disabling the "New character" button, then updated the PlayerHub to lock the button when the user hasn't joined any games.

### Implementation Details

#### 1. CharacterList Component Enhancement

**File**: `packages/ui/src/components/CharacterList.tsx`

**Added Props**:
```typescript
export interface CharacterListProps {
  // ... existing props
  disableCreate?: boolean;
  disableCreateReason?: string;
}
```

**Button Behavior**:
- **Enabled State** (user has games):
  - Green background (`bg-brand-500`)
  - White text
  - Hover effect (`hover:bg-brand-600`)
  - Clickable cursor

- **Disabled State** (no games):
  - Gray background (`bg-slate-100` / `bg-slate-800`)
  - Muted text (`text-slate-400` / `text-slate-500`)
  - Not-allowed cursor (`cursor-not-allowed`)
  - Tooltip on hover explaining why it's disabled

**Modified Code** (Lines 52-72):
```typescript
<div className="relative group">
  <button
    type="button"
    onClick={onCreateClick}
    disabled={disableCreate}
    className={cn(
      "rounded-md border px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
      disableCreate
        ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500"
        : "border-transparent bg-brand-500 text-white hover:bg-brand-600"
    )}
    aria-disabled={disableCreate}
  >
    New character
  </button>
  {disableCreate && disableCreateReason ? (
    <div className="pointer-events-none absolute right-0 top-full z-10 mt-1 hidden w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-lg group-hover:block dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
      {disableCreateReason}
    </div>
  ) : null}
</div>
```

**Tooltip Behavior**:
- Hidden by default
- Shows on hover when button is disabled
- Positioned below button with shadow
- Contains explanation text
- Dark mode compatible

#### 2. PlayerHub Integration

**File**: `apps/web/components/player/player-hub.tsx`

**Added Logic** (Line 166):
```typescript
const hasGames = games.length > 0;
```

**Updated CharacterList Usage** (Lines 422-439):
```typescript
<CharacterList
  characters={characters}
  selectedId={activeCharacterId}
  onSelect={handleSelectCharacter}
  onCreateClick={() => setCreateDialogOpen(true)}
  disableCreate={!hasGames}  // ← Disable if no games
  disableCreateReason={
    !hasGames
      ? "You must join a game before creating a character. Use the 'Join game' button to enter an invite code."
      : undefined
  }
  emptyState={
    <p>
      Create a hero to start tracking sessions and source
      permissions.
    </p>
  }
/>
```

---

## User Experience

### Scenario 1: New User (No Games)

**State**: User has not joined any games

**UI Behavior**:
```
┌─ Characters ──────────────────────────────┐
│                                            │
│  No characters yet.                        │
│  Create one to personalize sheets and     │
│  source permissions.                       │
│                                            │
│                        [ New character ]   │ ← DISABLED (grayed out)
│                        (hover shows tooltip)
└────────────────────────────────────────────┘

Tooltip on hover:
┌────────────────────────────────────────────┐
│ You must join a game before creating a    │
│ character. Use the 'Join game' button to  │
│ enter an invite code.                     │
└────────────────────────────────────────────┘
```

**Actions Available**:
- ✅ Can click "Join game" to enter invite code
- ❌ Cannot click "New character" (disabled)

### Scenario 2: Player Joins Game

**State**: User clicks "Join game" and successfully joins

**UI Behavior**:
```
1. User clicks "Join game"
2. Enters valid invite code
3. Game added to "Games" list
4. "New character" button becomes ENABLED ✅
5. User can now create characters
```

### Scenario 3: Existing Player (Has Games)

**State**: User is already part of one or more games

**UI Behavior**:
```
┌─ Characters ──────────────────────────────┐
│                                            │
│  ● Thorin · L5 Fighter                    │
│    System: dnd-5e                         │
│    Linked game: abc-123                   │
│                                            │
│                        [ New character ]   │ ← ENABLED (clickable)
└────────────────────────────────────────────┘
```

**Actions Available**:
- ✅ Can create new characters
- ✅ Can select existing characters
- ✅ Can switch between games

---

## Technical Flow

### Game Join → Button Enable Flow

```
1. User clicks "Join game" button
   ↓
2. JoinGameDialog opens
   ↓
3. User enters invite code
   ↓
4. joinGameMutation.mutateAsync(inviteCode)
   ↓
5. API call: POST /api/v1/games/join
   ↓
6. Success: Game added to games array
   ↓
7. gamesQuery.data updates
   ↓
8. hasGames becomes true
   ↓
9. disableCreate becomes false
   ↓
10. "New character" button enabled ✅
```

### Character Creation Flow (When Enabled)

```
1. User clicks "New character" (enabled)
   ↓
2. CharacterCreateDialog opens
   ↓
3. User fills in character details
   ↓
4. createCharacterMutation.mutateAsync(payload)
   ↓
5. API call: POST /api/v1/characters
   ↓
6. Success: Character created with gameId link
   ↓
7. Character appears in list
```

---

## Edge Cases Handled

### 1. User Leaves All Games

**Scenario**: User was in games, but left all of them

```typescript
const hasGames = games.length > 0;  // ← Becomes false
// Button automatically disables
```

**Result**: "New character" button becomes disabled again ✅

### 2. Multiple Games

**Scenario**: User is part of multiple games

```typescript
games = [game1, game2, game3]
hasGames = true  // ← Any games = enabled
```

**Result**: Button stays enabled, user can create characters for any game ✅

### 3. Loading State

**Scenario**: Games are still loading from API

```typescript
const isLoading = gamesQuery.isLoading;

// Button shows in loading skeleton
// Once loaded, hasGames determined
```

**Result**: Button state determined after data loads ✅

### 4. Network Error

**Scenario**: Games fail to load due to network error

```typescript
gamesQuery.isError = true
games = []  // ← Falls back to empty array
hasGames = false
```

**Result**: Button disabled (safe default) ✅

---

## Accessibility

### Keyboard Navigation
```
Tab → Focus "New character" button
Enter/Space → (if enabled) Opens dialog
               (if disabled) No action, tooltip visible
```

### Screen Reader Support
```html
<button
  type="button"
  disabled={true}
  aria-disabled="true"
>
  New character
</button>
```

**Announced**: "New character, button, disabled"

### Tooltip Accessibility
- Tooltip uses `pointer-events-none` (doesn't interfere with interaction)
- Shows on hover (visual feedback)
- Content explains reason for disabled state
- High contrast in both light and dark modes

---

## Testing

### Test 1: New User Flow

**Steps**:
```
1. Create new account or sign in as new user
2. Navigate to Player Hub (/player)
3. ✅ Expected: "New character" button is grayed out
4. Hover over button
5. ✅ Expected: Tooltip shows: "You must join a game before creating a character..."
6. Click button
7. ✅ Expected: Nothing happens (disabled)
```

### Test 2: Join Game → Enable Button

**Steps**:
```
1. Start with no games (button disabled)
2. Click "Join game"
3. Enter valid invite code: "test-game-123"
4. Click "Join"
5. ✅ Expected: Game added to list
6. ✅ Expected: "New character" button becomes enabled (green)
7. Click "New character"
8. ✅ Expected: Create dialog opens
```

### Test 3: Create Character After Joining

**Steps**:
```
1. Have at least one game joined
2. Click "New character" (enabled)
3. Fill in character details:
   - Name: "Aragorn"
   - Class: "Ranger"
   - Level: 1
   - System: "dnd-5e"
4. Click "Create"
5. ✅ Expected: Character created successfully
6. ✅ Expected: Character appears in list with game link
```

### Test 4: Leave All Games → Disable Button

**Steps**:
```
1. Have games and characters
2. Leave all games (via game management)
3. ✅ Expected: "New character" button becomes disabled
4. ✅ Expected: Tooltip explains need to join game
```

### Test 5: Dark Mode Compatibility

**Steps**:
```
1. Go to Settings → Change theme to "Dark"
2. Navigate to Player Hub
3. ✅ Expected: Disabled button has dark mode styling
4. Hover over disabled button
5. ✅ Expected: Tooltip has dark mode styling with proper contrast
```

---

## Business Logic

### Why Characters Require Games

1. **Game Context**: Characters need game context for:
   - Source permissions (campaign books/modules)
   - Session tracking
   - GM-player relationships
   - Character sheets customization

2. **Data Integrity**: Prevents orphaned characters without game links

3. **User Guidance**: Forces users to understand the game-first workflow

4. **Multiplayer Design**: TTRPG Center is designed for group play, not solo characters

---

## Alternative Approaches Considered

### Approach 1: Allow Character Creation, Assign Later
**Pros**: More flexible, users can experiment
**Cons**: Orphaned characters, confusing UX, no game context
**Decision**: ❌ Rejected - violates multiplayer-first design

### Approach 2: Auto-Create Default Game
**Pros**: No blocking, seamless onboarding
**Cons**: Clutters games list, confusing for users who want to join existing games
**Decision**: ❌ Rejected - forces unwanted data

### ✅ Approach 3: Lock Until Game Joined (Chosen)
**Pros**:
- Clear workflow (game → character)
- Prevents orphaned data
- Guides users to correct flow
- Tooltip provides clear instructions

**Cons**:
- One extra step for new users
- Slightly more friction

**Decision**: ✅ Accepted - best balance of UX and data integrity

---

## Future Enhancements

### Possible Improvements
1. **Quick Join Shortcut**: Add "Join game first" button in tooltip that opens join dialog
2. **Game Suggestions**: Show popular/public games to join
3. **Solo Mode**: Special "Practice" game for solo character creation (future feature)
4. **Onboarding Flow**: Guided tutorial for new users explaining game→character flow

---

## Files Modified

1. **`packages/ui/src/components/CharacterList.tsx`** - Added disable props and tooltip
2. **`apps/web/components/player/player-hub.tsx`** - Added game check logic

**No database changes required** - Pure UI/logic enhancement.

---

## Success Criteria

- ✅ "New character" button disabled when user has no games
- ✅ Tooltip explains why button is disabled
- ✅ Button enables immediately when user joins a game
- ✅ Button disables again if user leaves all games
- ✅ Accessibility support (aria-disabled, keyboard navigation)
- ✅ Dark mode compatible
- ✅ No breaking changes to existing functionality

---

**Status**: ✅ COMPLETE

The "New Character" button on the Player Hub now properly locks until the player joins a game, with clear visual feedback and helpful guidance.

---

**Related Documentation**:
- Account Settings Fixes: `ACCOUNT_SETTINGS_FIXES.md`
- **This Document**: `CHARACTER_CREATION_GAME_LOCK.md`
