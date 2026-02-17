# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Docker (Recommended)
```bash
# Start all services (MongoDB, Backend, Frontend)
docker compose up -d

# View logs
docker compose logs -f [service_name]

# Rebuild after changes
docker compose up -d --build

# Stop all services
docker compose down
```

### Backend (Manual)
```bash
cd backend

# Setup
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest
```

### Frontend (Manual)
```bash
cd frontend

# Setup
npm install

# Development
npm run dev          # Start dev server on port 3000
npm run build        # Build for production
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

## Architecture

### Backend Structure (FastAPI + MongoDB)

**Three-layer architecture** - strictly separate concerns:

1. **Routes** (`app/api/v1/`) - HTTP handling, request/response serialization
2. **Services** (`app/services/`) - Business logic, orchestration
3. **Repositories** (`app/repositories/`) - Database operations only

Key patterns:
- **Database**: Motor async MongoDB client singleton in `app/core/database.py`
- **Configuration**: Pydantic Settings in `app/core/config.py` (loads from .env)
- **Response formatting**: Always use helpers from `app/utils/response.py`:
  - `success_response(data, message)` for successful responses
  - `error_response(code, message, details)` for errors
  - `paginated_response(data, page, limit, total)` for lists
- **API versioning**: All routes under `/api/v1/` prefix
- **Auth**: Session-based (HTTP-only cookies), managed by `auth_service.py`
- **Models**: Pydantic models in `app/models/` for validation and serialization

**Adding new endpoints:**
1. Create route handler in `app/api/v1/{resource}.py`
2. Create service in `app/services/{resource}_service.py` for business logic
3. Create repository in `app/repositories/{resource}_repository.py` for DB access
4. Register router in `app/api/v1/__init__.py`
5. Use response helpers - never return raw dicts

### Frontend Structure (React + TypeScript)

**Directory organization:**
- `pages/` - Route-level components (one per URL)
- `components/` - Reusable UI components
- `services/` - API client functions (one file per resource)
- `contexts/` - React Context providers (AuthContext provides user state)
- `types/` - TypeScript interfaces
- `hooks/` - Custom React hooks
- `utils/` - Helper functions

**Routing:**
- Public routes: `/`, `/features`, `/about`, `/pricing`
- Auth routes: `/signin`, `/signup` (redirect to `/home` if authenticated)
- Protected routes: `/home` (requires authentication, redirects to `/signin` if not)
- Use `<ProtectedRoute>` wrapper for authenticated pages
- Use `<PublicRoute>` wrapper for public pages

**Authentication:**
- `AuthContext` provides `user`, `login()`, `logout()`, `register()`
- Session token stored in HTTP-only cookie (managed by backend)
- Check `user` from context to determine auth state

**API calls:**
- All API services in `src/services/` use axios client from `services/api.ts`
- API client automatically includes credentials (cookies)
- Base URL from `VITE_API_URL` env var (defaults to `http://localhost:8000`)

## Data Standards

### API Response Format
All endpoints return consistent structure (defined in `backend/app/utils/response.py`):

**Success:**
```json
{
  "success": true,
  "data": {},
  "message": "Success message",
  "timestamp": "2026-01-19T10:00:00Z"
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "User-friendly message",
    "details": {}
  },
  "timestamp": "2026-01-19T10:00:00Z"
}
```

**Paginated:**
```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "total_pages": 5
  },
  "timestamp": "2026-01-19T10:00:00Z"
}
```

### Other Data Conventions
- **Timestamps**: Store in UTC, ISO 8601 format. Field names: `created_at`, `updated_at`
- **Monetary values**: Store as integers in smallest currency unit (paise/cents). Field suffix: `_amount`
- **Database IDs**: MongoDB ObjectId as `_id`
- **Phone numbers**: Store with country code in E.164 format

## Naming Conventions

- **API endpoints**: `/api/v1/{resource}/{action}` (plural nouns, kebab-case)
- **MongoDB collections**: plural snake_case (e.g., `menu_items`, `orders`)
- **Python**: snake_case for functions/variables, PascalCase for classes
- **TypeScript**: camelCase for functions/variables, PascalCase for components/types
- **React components**: PascalCase files (e.g., `HomePage.tsx`)
- **Constants**: UPPERCASE_WITH_UNDERSCORES in both languages
- **Environment variables**: UPPERCASE_WITH_UNDERSCORES

## Role-Based Access Control

The system has different user roles (defined in `backend/app/models/user.py`):
- Staff roles determine which features are accessible in `/home` page
- HomePage uses role-based tabs to show different views

## Environment Variables

### Backend (.env)
- `MONGODB_URI` - MongoDB connection string (default: `mongodb://localhost:27017`)
- `DB_NAME` - Database name (default: `ahar_pos`)
- `FRONTEND_URL` - Frontend URL for CORS (default: `http://localhost:3000`)
- `API_PORT` - Backend port (default: `8000`)
- `DEBUG` - Enable debug mode (default: `false`)
- `SESSION_EXPIRE_HOURS` - Session expiration time (default: `24`)

### Frontend (.env)
- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Code Quality Requirements

### Python
- Follow PEP 8, max line length 100
- Use type hints for function parameters and returns
- Use async/await for I/O operations
- Add docstrings to public functions and classes

### TypeScript
- Enable strict mode
- Define interfaces for all data structures
- Avoid `any` type

### General
- Keep functions under 50 lines
- Max nesting depth: 3-4 levels
- Use early returns to reduce nesting
- Comment "why" not "what"

## Git Commit Format
```
<type>: <description>

Types: feat, fix, refactor, docs, style, test, chore
Example: feat: add user authentication endpoint
```

## Testing

Backend uses pytest with async support:
```bash
cd backend
pytest                    # Run all tests
pytest tests/test_*.py    # Run specific test file
pytest -v                 # Verbose output
```

## Access Points

When services are running:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- API Docs (ReDoc): http://localhost:8000/redoc
- MongoDB: localhost:27017
