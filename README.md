# Ahar.AI - Restaurant POS System

An AI-powered Point of Sale system for restaurants, built with modern technologies.

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Backend**: Python + FastAPI
- **Database**: MongoDB
- **AI**: Placeholder for future AI agent capabilities

## Project Structure

```
Ahar.AI/
├── frontend/           # React TypeScript application
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   ├── pages/      # Route-level components
│   │   ├── services/   # API call functions
│   │   ├── hooks/      # Custom React hooks
│   │   ├── utils/      # Helper functions
│   │   ├── constants/  # Enums, config values
│   │   ├── types/      # TypeScript interfaces
│   │   ├── contexts/   # React Context providers
│   │   └── assets/     # Static files
│   └── ...
│
├── backend/            # FastAPI Python application
│   ├── app/
│   │   ├── api/        # API route handlers
│   │   ├── models/     # Pydantic models
│   │   ├── services/   # Business logic layer
│   │   ├── repositories/ # Database access layer
│   │   ├── ai/         # AI agent module
│   │   ├── core/       # Configuration
│   │   └── utils/      # Helper functions
│   └── tests/
│
├── docs/            # Project documentation (guides, API, features, plans)
└── README.md
```

## Documentation

Detailed docs (guides, data specs, API, features, plans) live in **[docs/](docs/)**. See [docs/README.md](docs/README.md) for the index.

## Prerequisites

- Docker & Docker Compose (recommended)
- Or for manual setup:
  - Node.js 18+
  - Python 3.11+
  - MongoDB 6.0+

## Quick Start with Docker

The easiest way to run the entire stack:

```bash
# Start all services (MongoDB, Backend, Frontend)
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

Once running, access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Docker Commands Reference

| Action | Command |
|--------|---------|
| Start all services | `docker compose up -d` |
| Stop all services | `docker compose down` |
| Restart all services | `docker compose restart` |
| Restart single service | `docker compose restart backend` |
| View all logs | `docker compose logs -f` |
| View backend logs | `docker compose logs -f backend` |
| Rebuild after code changes | `docker compose up -d --build` |
| Stop and remove volumes | `docker compose down -v` |
| Check service status | `docker compose ps` |

## Manual Setup (Without Docker)

### Clone the repository

```bash
git clone <repository-url>
cd Ahar.AI
```

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Edit .env with your configuration

# Run the development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install

# Create .env file (optional, for custom API URL)
echo "VITE_API_URL=http://localhost:8000" > .env

# Run the development server
npm run dev
```

### Database Setup

Ensure MongoDB is running locally on port 27017, or configure `MONGODB_URI` in your `.env` file.

```bash
# Using Docker (optional)
docker run -d -p 27017:27017 --name mongodb mongo:6.0
```

## Development

### Port Assignments

| Service  | Port  |
|----------|-------|
| Frontend | 3000  |
| Backend  | 8000  |
| MongoDB  | 27017 |

### API Documentation

Once the backend is running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Environment Variables

#### Backend (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | `ahar_pos` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:3000` |
| `API_PORT` | Backend port | `8000` |
| `DEBUG` | Enable debug mode | `false` |
| `AI_ENABLED` | Enable AI features | `false` |

#### Frontend (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `http://localhost:8000` |

## API Response Format

All API responses follow a consistent structure:

### Success Response
```json
{
  "success": true,
  "data": {},
  "message": "Success message",
  "timestamp": "2026-01-19T10:00:00Z"
}
```

### Error Response
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

## License

Private - All rights reserved.
