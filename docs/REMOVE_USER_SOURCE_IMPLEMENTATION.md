# Remove User Source - Implementation Complete

## Overview
Implemented the ability for users to remove sources from their available sources list with confirmation dialog.

## Backend Implementation

### New Endpoint: `DELETE /api/v1/sources/{id}`

**File:** `apps/web/app/api/v1/sources/[id]/route.ts`

**Authentication:** Required (401 if not authenticated)

**Functionality:**
- Removes the association between the authenticated user and the specified source
- Does NOT delete the source from the database
- Returns the updated list of the user's owned sources

**Status Codes:**
- `200 OK` - Source successfully removed, returns updated list
- `401 Unauthorized` - User not authenticated
- `403 Forbidden` - User doesn't own this source
- `404 Not Found` - Source doesn't exist
- `500 Internal Server Error` - Server error

**Example Response:**
```json
[
  {
    "id": "source-1",
    "name": "Player's Handbook",
    "category": "Core Rules",
    "owned": true,
    "updatedAt": "2024-01-01T00:00:00Z"
  }
]
```

## Frontend Implementation

### Components

1. **RemoveSourceDialog** (`apps/web/components/gm/remove-source-dialog.tsx`)
   - Confirmation dialog that asks user to confirm removal
   - Shows source name and warning about removal
   - Cancel and Remove buttons

2. **GM Hub Updates** (`apps/web/components/gm/gm-hub.tsx`)
   - Added `removeUserSourceMutation` for API calls
   - Added `handleOwnedSourcesChange` to detect when sources are deselected
   - Added dialog state management
   - Wired up SourceMultiSelect to trigger confirmation

### API Client

**File:** `packages/api/src/index.ts`

```typescript
async removeUserSource(sourceId: string): Promise<Source[]> {
  return this.request<Source[]>(`/sources/${sourceId}`, {
    method: "DELETE"
  });
}
```

## User Flow

1. User clicks on a source in the "Available sources" section
2. Confirmation dialog appears: "Remove source?"
3. Dialog shows source name and warning
4. User can:
   - Click "Cancel" - closes dialog, no changes
   - Click "Remove source" - removes source from their list
5. On success:
   - Toast notification: "Source removed"
   - Source removed from Available Sources display
   - Cache updated automatically
6. On error:
   - Error banner displayed with message

## Testing

### Manual Testing Checklist
- [ ] Click on owned source → confirmation dialog appears
- [ ] Click "Cancel" → dialog closes, no changes
- [ ] Click "Remove source" → source removed, success toast shown
- [ ] Verify source no longer appears in Available Sources
- [ ] Verify source still exists in database (can be re-added)
- [ ] Try removing non-owned source → 403 error
- [ ] Try removing non-existent source → 404 error
- [ ] Try removing while not authenticated → 401 error

### Database Verification
```sql
-- Check user_sources table
SELECT * FROM user_sources WHERE user_id = '{userId}' AND source_id = '{sourceId}';
-- Should return no rows after removal

-- Check sources table
SELECT * FROM sources WHERE id = '{sourceId}';
-- Should still exist
```

## Future Enhancements

1. **Cascade Removal:** Consider removing source from user's games when removed from available sources
2. **Bulk Removal:** Allow removing multiple sources at once
3. **Undo Feature:** Add ability to undo removal within a time window
4. **Activity Log:** Track when sources are added/removed for audit purposes

## Related Files

- Backend: `apps/web/app/api/v1/sources/[id]/route.ts`
- Frontend Dialog: `apps/web/components/gm/remove-source-dialog.tsx`
- Frontend Logic: `apps/web/components/gm/gm-hub.tsx`
- API Client: `packages/api/src/index.ts`
- Types: `@ttrpg-center/types` (Source interface)
