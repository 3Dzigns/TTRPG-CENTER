# Player Hub Cleanup & Label Changes

**Date**: 2025-11-06
**Changes**: Mock data removal, label updates, button disable feature
**Status**: ✅ COMPLETE

---

## Changes Summary

### 1. ✅ New Character Button Disable (Already Implemented)
**Status**: Previously implemented earlier in session
**File**: `apps/web/components/player/player-hub.tsx` (lines 427-432)

The "New Character" button is already disabled when users haven't joined any games, with a helpful tooltip explaining they need to join a game first.

### 2. ✅ Mock Games Removed from Database
**Status**: Completed

**Removed Games**:
1. **"Shadows over Neverwinter"**
   - ID: `660e8400-e29b-41d4-a716-446655440001`
   - Status: Active
   - Session Count: 12

2. **"Echoes of the Astral Sea"**
   - ID: `660e8400-e29b-41d4-a716-446655440002`
   - Status: Draft
   - Session Count: 0

**Database Cleanup Actions**:
```sql
-- Deleted 2 game_members entries
DELETE FROM game_members WHERE game_id IN ('660e8400...001', '660e8400...002');

-- Deleted 3 game_sources entries
DELETE FROM game_sources WHERE game_id IN ('660e8400...001', '660e8400...002');

-- Deleted 2 mock games
DELETE FROM games WHERE id IN ('660e8400...001', '660e8400...002');

-- Result: 0 remaining games (clean slate)
```

### 3. ✅ Label Changed: "Joined Games" → "Active Games"
**Status**: Completed
**File**: `packages/ui/src/components/GameList.tsx` (line 36)

**Before**:
```tsx
<h2>Joined Games</h2>
```

**After**:
```tsx
<h2>Active Games</h2>
```

---

## User Experience Changes

### Before Fix

**Active Games Section**:
```
┌─ Joined Games ────────────────────┐  ← Old label
│                                    │
│  ● Shadows over Neverwinter       │  ← Mock game 1
│    Sessions: 12                    │
│                                    │
│  ● Echoes of the Astral Sea        │  ← Mock game 2
│    Sessions: 0                     │
│                                    │
│              [Join with code]      │
└────────────────────────────────────┘
```

### After Fix

**Active Games Section**:
```
┌─ Active Games ────────────────────┐  ← New label
│                                    │
│  No games joined yet.             │  ← Empty state (clean)
│  Ask your GM for an invite code   │
│  to join a campaign.              │
│                                    │
│              [Join with code]      │
└────────────────────────────────────┘
```

**Characters Section** (already fixed):
```
┌─ Characters ──────────────────────┐
│                                    │
│  No characters yet.               │
│                                    │
│          [ New character ]         │  ← Disabled until game joined
│          (hover shows tooltip)    │
└────────────────────────────────────┘
```

---

## Why These Changes Matter

### 1. Mock Data Removal
**Problem**: Mock games with fake titles confused users and cluttered the interface
**Solution**: Clean database with only real games
**Benefit**: Users see accurate game state, can start fresh

### 2. Label Change: "Joined Games" → "Active Games"
**Reason**:
- "Active Games" better reflects games currently being played
- Distinguishes from archived/completed games
- More intuitive terminology for players
- Aligns with game status field (draft/active/archived)

### 3. New Character Button Disable
**Reason**:
- Prevents orphaned characters without game context
- Guides users through correct workflow: Join game → Create character
- Clear tooltip explains what users need to do

---

## Technical Details

### Database Schema
The cleanup affected three tables:

**games**:
- Primary table for game records
- Contains game metadata (title, status, GM, etc.)

**game_members**:
- Junction table linking users to games
- Tracks membership roles (GM, co-GM, player, spectator)
- Cascading delete removes memberships when game deleted

**game_sources**:
- Junction table linking games to content sources
- Tracks which rulebooks/modules are active for each game
- Cascading delete removes associations when game deleted

### Foreign Key Constraints
```sql
-- game_members has FK to games
ALTER TABLE game_members
  ADD CONSTRAINT game_members_game_id_fkey
  FOREIGN KEY (game_id) REFERENCES games(id)
  ON DELETE CASCADE;

-- game_sources has FK to games
ALTER TABLE game_sources
  ADD CONSTRAINT game_sources_game_id_fkey
  FOREIGN KEY (game_id) REFERENCES games(id)
  ON DELETE CASCADE;
```

**Note**: We manually deleted related records first to be explicit, but CASCADE would handle it automatically.

---

## Testing

### Test 1: Verify Mock Games Removed

**Steps**:
```bash
# Check games table is empty
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "SELECT * FROM games;"

# Expected: 0 rows
```

**Result**: ✅ No games in database

### Test 2: Verify Label Change

**Steps**:
1. Navigate to Player Hub (`/player`)
2. Look at the games section header
3. ✅ Expected: Header shows "Active Games" (not "Joined Games")

### Test 3: Verify Empty State

**Steps**:
1. Navigate to Player Hub with no games joined
2. ✅ Expected: Empty state shows "No games joined yet"
3. ✅ Expected: "New character" button is disabled with tooltip

### Test 4: Join Real Game Flow

**Steps**:
1. Click "Join with code"
2. Enter valid invite code
3. ✅ Expected: Game appears under "Active Games"
4. ✅ Expected: "New character" button becomes enabled

---

## Related Components

### GameList Component
**Location**: `packages/ui/src/components/GameList.tsx`
**Purpose**: Reusable component displaying games list
**Props**:
- `games`: Array of game objects
- `activeGameId`: Currently selected game ID
- `onSelect`: Callback when game clicked
- `onJoinClick`: Callback for "Join with code" button

### CharacterList Component
**Location**: `packages/ui/src/components/CharacterList.tsx`
**Purpose**: Reusable component displaying characters list
**Props**:
- `characters`: Array of character objects
- `disableCreate`: Disables "New character" button
- `disableCreateReason`: Tooltip text for disabled button

### PlayerHub Container
**Location**: `apps/web/components/player/player-hub.tsx`
**Purpose**: Main Player Hub page orchestrating games and characters
**Logic**:
- Fetches games via API (`/api/v1/games`)
- Determines `hasGames` for button enable/disable
- Passes data to GameList and CharacterList components

---

## Files Modified

1. **`packages/ui/src/components/GameList.tsx`** - Changed label from "Joined Games" to "Active Games"

**Database Changes**:
- Deleted 2 game_members records
- Deleted 3 game_sources records
- Deleted 2 mock games from games table

**No Code Changes Needed** for:
- New Character button disable (already implemented)

---

## Migration Safety

### For Existing Users
**Mock Games Impact**: Only affected development/test users who had mock games
**Real Games**: No impact - only specific mock game IDs were deleted

### Data Integrity
- Foreign key constraints ensure referential integrity
- Cascading deletes prevent orphaned records
- No impact on characters (characters reference games via nullable `game_id`)

### Rollback Plan
If mock games needed to be restored:
```sql
-- Restore mock games (not recommended)
INSERT INTO games (id, title, status, gm_id, session_count, created_at, updated_at)
VALUES
  ('660e8400-e29b-41d4-a716-446655440001', 'Shadows over Neverwinter', 'active', '<gm_id>', 12, NOW(), NOW()),
  ('660e8400-e29b-41d4-a716-446655440002', 'Echoes of the Astral Sea', 'draft', '<gm_id>', 0, NOW(), NOW());
```

---

## Success Criteria

- ✅ Mock games removed from database
- ✅ "Active Games" label displayed instead of "Joined Games"
- ✅ "New character" button disabled when no games joined (already working)
- ✅ Empty state shows helpful message
- ✅ No breaking changes for existing functionality
- ✅ Database integrity maintained

---

## User Workflow (Complete)

### Fresh User Experience:
```
1. User navigates to Player Hub
   ↓
2. Sees "Active Games" section (empty)
   ↓
3. Clicks "Join with code"
   ↓
4. Enters invite code from GM
   ↓
5. Game appears under "Active Games" ✅
   ↓
6. "New character" button becomes enabled ✅
   ↓
7. User creates character linked to game ✅
```

---

**Status**: ✅ COMPLETE

All three requested changes have been implemented:
1. New Character button disable feature (already working)
2. Mock games removed from database
3. Label changed from "Joined Games" to "Active Games"

---

**Related Documentation**:
- Character Creation Lock: `CHARACTER_CREATION_GAME_LOCK.md`
- **This Document**: `PLAYER_HUB_CLEANUP.md`
