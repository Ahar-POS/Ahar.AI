# Create Home Page with Role-Based Tab Navigation

## TL;DR
Build a home/dashboard page that appears after login, with tab navigation (Kitchen, Waiter, Tables, Menu, Staff, Reports, Analytics, Settings) that respects user role permissions. Tab visibility will be controlled by permissions (to be implemented later), but the structure should be ready.

## Current State
- After successful login, users are redirected to `/` which currently shows `LandingPage`
- No protected routes or home page exists
- User roles exist in the system (`admin` currently, with future roles planned: `waiter`, `chef`, `cashier`)
- Authentication context provides user data including `role`
- No navigation structure for authenticated users

## Expected Outcome
- Create a new `HomePage` component that serves as the main dashboard
- Implement tab navigation bar with tabs: Kitchen, Waiter, Tables, Menu, Staff, Reports, Analytics, Settings
- Tabs should be conditionally visible based on user role (permission system to be added later)
- For now, all tabs visible to all authenticated users (admin)
- Each tab should route to a placeholder page/component (don't build features yet)
- Protected route wrapper to redirect unauthenticated users to `/signin`
- After login, redirect to `/home` or `/dashboard` instead of `/`

## Relevant Files
- `frontend/src/pages/HomePage.tsx` (new)
- `frontend/src/App.tsx` (update routing, add protected routes)
- `frontend/src/components/ProtectedRoute.tsx` (new - optional helper)
- `frontend/src/pages/SignInPage.tsx` (update redirect path)
- `frontend/src/pages/SignUpPage.tsx` (update redirect path)
- `frontend/src/components/TabNavigation.tsx` (new - tab bar component)

## Implementation Notes
- Use React Router for tab navigation
- Tab visibility logic should be prepared for future permission system (e.g., `hasPermission(tabName)`)
- Create placeholder components for each tab section (e.g., `KitchenPage`, `MenuPage`, etc.)
- Consider creating a layout component that wraps authenticated pages with the tab navigation
- Tab navigation should be responsive and match the design system

## Type
Feature

## Priority
High (blocks user flow after authentication)

## Effort
Medium (2-3 hours)

## Dependencies
- Authentication system (✅ exists)
- User role system (✅ exists, needs permission expansion later)
- Routing setup (✅ exists, needs protected routes)

## Progress
- ✅ Route guards + `/home` routing
- ✅ Home page layout + tab navigation
- ✅ Redirect updates + public page access rules
- ✅ Styling polish + mobile tab bar
- ✅ 🔐 Admin-only Staff tab with staff user creation
- ✅ 👥 Staff role added (backend + frontend types)
- ✅ 🧭 Role-based tab visibility for admin vs staff

Overall progress: 100% 🎉
