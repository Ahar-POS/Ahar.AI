# Multi-Tenancy Data Isolation Issue

**Type:** Feature/Architecture  
**Priority:** High  
**Effort:** Large

---

## TL;DR

Currently, all users share the same restaurant data (tables, menus, orders). Each admin user should have their own isolated restaurant with separate tables, menus, and orders. The system needs to automatically filter data based on the logged-in user's restaurant association.

---

## Current State vs Expected Outcome

### Current State ❌
- All users can access all restaurants' data if they know the `restaurant_id`
- `restaurant_id` must be manually passed in API requests (query params or request body)
- User model has no `restaurant_id` field
- No automatic data filtering based on logged-in user
- No authorization checks - any user can create/modify any restaurant's data
- Frontend likely passes `restaurant_id` manually or uses a hardcoded value

### Expected Outcome ✅
- Each user (admin) is associated with exactly one restaurant
- Users can only see/manage their own restaurant's data
- `restaurant_id` is automatically derived from the authenticated user's session
- All API endpoints automatically filter by the user's `restaurant_id`
- Users cannot access other restaurants' data even if they know the ID
- Frontend doesn't need to pass `restaurant_id` - it's handled automatically

---

## Relevant Files That Need Changes

### Backend Models
- `backend/app/models/user.py` - Add `restaurant_id` field to User model
- `backend/app/models/table.py` - Already has `restaurant_id`, but needs validation
- `backend/app/models/menu_item.py` - Already has `restaurant_id`, but needs validation
- `backend/app/models/order.py` - Already has `restaurant_id`, but needs validation

### Backend Repositories
- `backend/app/repositories/user_repository.py` - Update to handle `restaurant_id` in user creation/updates
- `backend/app/repositories/table_repository.py` - Add authorization checks
- `backend/app/repositories/session_repository.py` - May need to include `restaurant_id` in session data

### Backend API Routes
- `backend/app/api/v1/tables.py` - Remove `restaurant_id` from query params, derive from authenticated user
- `backend/app/api/v1/auth.py` - Include `restaurant_id` in login response
- Future menu/order API routes - Same pattern as tables

### Backend Core
- `backend/app/core/security.py` - May need helper to get current user's `restaurant_id`
- `backend/app/services/auth_service.py` - Include `restaurant_id` in session/user context

### Frontend
- `frontend/src/contexts/AuthContext.tsx` - Store `restaurant_id` in auth context
- `frontend/src/services/tables.ts` - Remove `restaurant_id` from API calls
- `frontend/src/services/api.ts` - Ensure auth headers are properly set
- All pages/components that pass `restaurant_id` manually

---

## Implementation Approach

### Phase 1: User-Restaurant Association
1. Add `restaurant_id: str` field to `UserBase` and `UserInDB` models
2. Update user creation to require `restaurant_id`
3. Add database migration/script to assign existing users to restaurants (or create default restaurants)
4. Update user repository to handle `restaurant_id`

### Phase 2: Authentication & Authorization
1. Include `restaurant_id` in JWT/session token payload
2. Create FastAPI dependency `get_current_user_restaurant_id()` that extracts `restaurant_id` from authenticated user
3. Update all API endpoints to use this dependency instead of query params
4. Add authorization checks: verify user can only access their own restaurant's data

### Phase 3: Repository Layer Updates
1. Update all repository methods to require `restaurant_id` parameter
2. Add validation: ensure `restaurant_id` matches user's restaurant before any operation
3. Update queries to always filter by `restaurant_id`

### Phase 4: API Route Updates
1. Remove `restaurant_id` from query parameters and request bodies
2. Inject `restaurant_id` from authenticated user via dependency
3. Pass `restaurant_id` to repository methods
4. Add 403 Forbidden responses if user tries to access wrong restaurant

### Phase 5: Frontend Updates
1. Store `restaurant_id` in auth context after login
2. Remove all manual `restaurant_id` passing from API service calls
3. Update components to rely on auth context instead

---

## Risks & Considerations

### Data Migration
- **Risk:** Existing users and data need to be migrated
- **Mitigation:** Create migration script that:
  - Creates a restaurant for each existing user (or assigns them to a default restaurant)
  - Updates all existing tables/menu items/orders with the correct `restaurant_id`

### Backward Compatibility
- **Risk:** Breaking changes to API contracts
- **Mitigation:** 
  - Document API changes clearly
  - Consider versioning API endpoints if needed
  - Update frontend in same deployment

### User Creation Flow
- **Risk:** How to handle user signup - who assigns `restaurant_id`?
- **Options:**
  - Option A: Super admin creates users and assigns restaurants
  - Option B: User creates restaurant during signup (one restaurant per user)
  - Option C: User selects/creates restaurant after signup

### Multi-Restaurant Users (Future)
- **Note:** Current design assumes one user = one restaurant
- **Future:** If users need to manage multiple restaurants, consider:
  - `restaurant_id` array in user model
  - Restaurant selection in UI
  - Context switching between restaurants

### Database Indexes
- **Action Required:** Ensure indexes exist on `restaurant_id` fields for performance:
  - `tables` collection: `restaurant_id` + `table_number` (compound index)
  - `menu_items` collection: `restaurant_id` index
  - `orders` collection: `restaurant_id` index
  - `users` collection: `restaurant_id` index

### Testing Considerations
- Test that users cannot access other restaurants' data
- Test that `restaurant_id` is automatically set correctly
- Test migration script with existing data
- Test user creation with `restaurant_id` assignment

---

## Database Schema Changes

### Users Collection
```python
# Add to UserBase model:
restaurant_id: str = Field(..., description="Restaurant this user belongs to")
```

### Indexes Needed
```javascript
// MongoDB indexes
db.users.createIndex({ "restaurant_id": 1 })
db.tables.createIndex({ "restaurant_id": 1, "table_number": 1 })
db.menu_items.createIndex({ "restaurant_id": 1 })
db.orders.createIndex({ "restaurant_id": 1 })
```

---

## Example API Changes

### Before (Current)
```python
@router.get("/tables")
async def get_tables(
    restaurant_id: str = Query(...),  # ❌ Manual, insecure
    ...
):
    tables = await repo.get_by_restaurant(restaurant_id)
```

### After (Expected)
```python
@router.get("/tables")
async def get_tables(
    restaurant_id: str = Depends(get_current_user_restaurant_id),  # ✅ Auto from auth
    ...
):
    tables = await repo.get_by_restaurant(restaurant_id)
```

---

## Dependencies

- Requires authentication system to be fully functional
- Requires session/JWT tokens to include user information
- May require database migration tools/scripts

---

## Related Issues

- Authentication/authorization implementation
- Session management
- API security hardening

---

**Created:** 2026-01-22  
**Status:** Open  
**Assignee:** TBD
