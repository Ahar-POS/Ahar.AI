# Production Deployment Guide

**Last Updated:** 2026-03-19
**Status:** Production Ready ✅

This document details the complete production setup for Ahar.AI, including system architecture, deployment process, configurations, and troubleshooting.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Infrastructure Components](#infrastructure-components)
3. [Deployment Process](#deployment-process)
4. [Configuration Details](#configuration-details)
5. [Issues Encountered & Solutions](#issues-encountered--solutions)
6. [Security Considerations](#security-considerations)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## System Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────┬───────────────────────────────┬────────────────┘
             │                               │
             │                               │
    ┌────────▼────────┐            ┌────────▼────────┐
    │   Firebase      │            │  Google Cloud   │
    │   Hosting       │            │     Run         │
    │  (Frontend)     │            │   (Backend)     │
    │                 │            │                 │
    │  React + Vite   │◄──────────►│  FastAPI        │
    │  TypeScript     │   HTTPS    │  Python 3.12    │
    └─────────────────┘            └────────┬────────┘
                                            │
                                            │ TLS/SSL
                                            │
                                   ┌────────▼────────┐
                                   │   MongoDB       │
                                   │     Atlas       │
                                   │   (Database)    │
                                   └─────────────────┘
```

### Technology Stack

**Frontend:**
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **Hosting:** Firebase Hosting
- **Domain:** ahar-6cbad.web.app

**Backend:**
- **Framework:** FastAPI (Python 3.12)
- **Server:** Uvicorn (ASGI)
- **Hosting:** Google Cloud Run (Serverless)
- **Container:** Docker (python:3.12-slim)
- **Region:** asia-south1 (Mumbai)

**Database:**
- **Type:** MongoDB Atlas (Cloud)
- **Driver:** Motor (async) + PyMongo 4.6.1
- **Region:** Mumbai (same as backend)
- **Connection:** TLS/SSL with certifi

**AI Services:**
- **Provider:** Anthropic Claude API
- **Models:** Haiku 4.5 (chatbot), Sonnet 4.5 (insights)

---

## Infrastructure Components

### 1. Frontend (Firebase Hosting)

**Service:** Firebase Hosting
**Project ID:** ahar-6cbad
**URL:** https://ahar-6cbad.web.app

**Configuration:**
- Static asset hosting with global CDN
- Automatic SSL/TLS certificates
- Deploy via `firebase deploy --only hosting`
- Build output: `frontend/dist/`

### 2. Backend (Google Cloud Run)

**Service Name:** ahar-backend
**Project ID:** ahar-6cbad
**Region:** asia-south1 (Mumbai)
**URL:** https://ahar-backend-weym6v5qna-el.a.run.app

**Specifications:**
- **CPU:** 2 vCPU
- **Memory:** 2 GiB
- **Timeout:** 300 seconds
- **Min Instances:** 0 (scales to zero)
- **Max Instances:** 10
- **Concurrency:** 80 requests per instance
- **Access:** Public (unauthenticated allowed)

**Container:**
- Base Image: `python:3.12-slim`
- Port: 8080 (Cloud Run requirement)
- Workers: 2 Uvicorn workers
- Healthcheck: `/api/v1/health`

### 3. Database (MongoDB Atlas)

**Cluster:** Cluster0
**Type:** Shared M0 (Free Tier)
**Region:** Mumbai
**Connection String:** `mongodb+srv://ahar_admin:***@cluster0.mfk2cuq.mongodb.net/?appName=Cluster0`

**Database:** ahar_pos

**Network Access:**
- Allowed IPs: `0.0.0.0/0` (all IPs)
- Security: Username/password authentication + TLS encryption

**Collections:**
- `users` - User accounts and roles
- `sessions` - Session tokens
- `menu_items` - Restaurant menu
- `orders` - Order history
- `inventory` - Stock management
- Additional ML/forecasting collections

---

## Deployment Process

### Prerequisites

1. **Google Cloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project ahar-6cbad
   ```

2. **Firebase CLI** installed and authenticated:
   ```bash
   firebase login
   ```

3. **MongoDB Atlas** account with cluster created

### Backend Deployment

**Script:** `deploy-backend.sh`

```bash
#!/bin/bash
./deploy-backend.sh
```

**What it does:**
1. Validates `gcloud` authentication
2. Enables required Google Cloud APIs:
   - Cloud Run API
   - Container Registry API
   - Cloud Build API
3. Builds Docker image from source using Cloud Build
4. Deploys to Cloud Run with environment variables
5. Returns service URL

**Manual deployment:**
```bash
cd backend

gcloud run deploy ahar-backend \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0
```

**Environment Variables:**
Set via:
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "KEY=VALUE"
```

### Frontend Deployment

**Build and deploy:**
```bash
cd frontend

# Clean build
rm -rf dist node_modules/.vite

# Build with production env
npm run build

# Deploy to Firebase
firebase deploy --only hosting
```

**What happens:**
1. Vite reads `.env.production` for `VITE_API_URL`
2. Builds optimized production bundle
3. Firebase CLI uploads to hosting
4. CDN caches and serves globally

---

## Configuration Details

### Backend Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `MONGODB_URI` | `mongodb+srv://ahar_admin:***@cluster0.mfk2cuq.mongodb.net/?appName=Cluster0` | MongoDB connection string |
| `DB_NAME` | `ahar_pos` | Database name |
| `FRONTEND_URL` | `https://ahar-6cbad.web.app` | CORS allowed origin |
| `DEBUG` | `false` | Disable debug mode in production |
| `SESSION_COOKIE_SECURE` | `true` | Require HTTPS for cookies |
| `SESSION_COOKIE_SAMESITE` | `none` | Allow cross-site cookies |
| `CLAUDE_API_KEY` | `sk-ant-api03-***` | Claude API authentication |

**View current variables:**
```bash
gcloud run services describe ahar-backend \
  --region asia-south1 \
  --format="yaml(spec.template.spec.containers[0].env)"
```

### Frontend Environment Variables

**File:** `frontend/.env.production`

```env
VITE_API_URL=https://ahar-backend-weym6v5qna-el.a.run.app
```

**Note:** This file is read at **build time**, not runtime. Changes require rebuild + redeploy.

### Session Cookie Configuration

**Purpose:** Maintain user authentication across requests

**Settings:**
- **Name:** `session_token`
- **HttpOnly:** `true` (prevents JavaScript access, XSS protection)
- **Secure:** `true` (HTTPS only)
- **SameSite:** `none` (allows cross-site requests)
- **Path:** `/` (available for all routes)
- **Max-Age:** Calculated from session expiry (default 24 hours)

**Why SameSite=none is required:**
- Frontend and backend are on different domains (cross-site)
- `SameSite=lax` (default) blocks cookies in cross-site POST requests
- `SameSite=none` + `Secure=true` allows cookies across sites with HTTPS

### CORS Configuration

**Backend:** `backend/app/main.py`

```python
allow_origins=[settings.FRONTEND_URL]  # https://ahar-6cbad.web.app
allow_credentials=True  # Allow cookies
allow_methods=["*"]  # All HTTP methods
allow_headers=["*"]  # All headers
```

---

## Issues Encountered & Solutions

### 1. MongoDB SSL Handshake Failure

**Error:**
```
pymongo.errors.ServerSelectionTimeoutError: SSL handshake failed:
[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error
```

**Root Cause:**
- `python:3.11-slim` Docker image had incomplete CA certificates
- PyMongo couldn't verify MongoDB Atlas SSL certificate

**Solution:**
1. Added `certifi` package to `requirements.txt` (provides Mozilla CA bundle)
2. Updated Motor client to use certifi:
   ```python
   import certifi
   db.client = AsyncIOMotorClient(
       settings.MONGODB_URI,
       tlsCAFile=certifi.where()
   )
   ```
3. Upgraded Docker base image to `python:3.12-slim`

**Files Changed:**
- `backend/requirements.txt` - Added `certifi>=2024.2.2`
- `backend/app/core/database.py` - Added `tlsCAFile=certifi.where()`
- `backend/Dockerfile` - Changed to `python:3.12-slim`
- `backend/Dockerfile.production` - Changed to `python:3.12-slim`

### 2. MONGODB_URI Environment Variable Not Set

**Error:**
```
ServerSelectionTimeoutError: localhost:27017: [Errno 111] Connection refused
```

**Root Cause:**
- Environment variable wasn't set in Cloud Run during initial deployment
- Backend defaulted to `localhost:27017`

**Solution:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --set-env-vars "MONGODB_URI=mongodb+srv://..."
```

### 3. CORS Error (401/403)

**Error:**
Frontend couldn't make requests to backend due to CORS policy violations.

**Root Cause:**
`FRONTEND_URL` environment variable not set correctly in production.

**Solution:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "FRONTEND_URL=https://ahar-6cbad.web.app"
```

### 4. Session Cookie Not Sent (401 Not Authenticated)

**Error:**
```json
{
  "error": {
    "code": "NOT_AUTHENTICATED",
    "message": "You are not logged in"
  }
}
```

**Root Cause:**
- `SameSite=lax` cookie policy blocks cross-site POST requests
- Frontend (`ahar-6cbad.web.app`) and backend (`ahar-backend-*.run.app`) are different domains

**Solution:**
Changed cookie setting to `SameSite=none` (requires `Secure=true`):
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "SESSION_COOKIE_SAMESITE=none"
```

### 5. Frontend Still Hitting localhost:8000

**Error:**
After deployment, frontend made requests to `localhost:8000` instead of production API.

**Root Cause:**
- Browser cached old JavaScript bundle
- Old bundle had `localhost:8000` hardcoded

**Solution:**
1. Rebuild frontend with production env:
   ```bash
   rm -rf dist node_modules/.vite
   npm run build
   ```
2. Redeploy to Firebase:
   ```bash
   firebase deploy --only hosting
   ```
3. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)

---

## Security Considerations

### 1. MongoDB Security

**Authentication:**
- Username: `ahar_admin`
- Password: Strong password with special characters
- URL-encoded in connection string (`%40` for `@`, `%24` for `$`)

**Network Access:**
- Current: `0.0.0.0/0` (allow all IPs)
- Relies on strong authentication + TLS encryption
- **Future Option:** Static IP with VPC + Cloud NAT for IP whitelisting

**Encryption:**
- TLS/SSL enabled on all connections
- Certificate verification via `certifi`

### 2. Session Security

**Cookie Protection:**
- `HttpOnly=true` - Prevents XSS attacks (no JavaScript access)
- `Secure=true` - HTTPS only transmission
- `SameSite=none` - Required for cross-site but still secure with HTTPS

**Session Management:**
- Tokens stored in HTTP-only cookies (not localStorage)
- Server-side session validation
- Automatic expiry (24 hours default)
- Secure token generation

### 3. API Security

**CORS:**
- Strict origin control (only `ahar-6cbad.web.app` allowed)
- Credentials required for authenticated endpoints

**Authentication:**
- Session-based authentication
- Admin-only endpoints protected with `get_admin_user` dependency
- Password hashing with bcrypt

**Rate Limiting:**
- Cloud Run auto-scales but limits concurrent requests
- Consider adding rate limiting middleware for production

### 4. Secrets Management

**Current:**
- Secrets stored as Cloud Run environment variables
- Not visible in logs or container inspection
- Accessible only to service account

**Best Practice:**
- Consider migrating to Google Secret Manager for:
  - Secret rotation
  - Access audit logs
  - Version control

### 5. API Keys

**Claude API Key:**
- Stored as environment variable
- Used for chatbot and insights features
- Rate limits enforced by Anthropic

**External API Keys (Optional):**
- Weather APIs, News APIs for ML forecasting
- Not yet set in production

---

## Monitoring & Maintenance

### Viewing Logs

**Cloud Run Logs:**
```bash
# View all logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend" --limit 50

# View errors only
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend AND severity>=ERROR" --limit 20

# View MongoDB connection logs
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend AND textPayload:"MongoDB"' --limit 10

# Stream logs in real-time
gcloud logging tail "resource.labels.service_name=ahar-backend"
```

**Firebase Hosting Logs:**
- Available in Firebase Console
- Includes CDN access logs and errors

### Health Checks

**Backend Health Endpoint:**
```bash
curl https://ahar-backend-weym6v5qna-el.a.run.app/api/v1/health
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "service": "Ahar.AI Restaurant POS",
    "version": "0.1.0"
  },
  "message": "Service is running",
  "timestamp": "2026-03-19T14:26:34.424520+00:00"
}
```

### Monitoring Dashboard

**Google Cloud Console:**
- URL: https://console.cloud.google.com/run?project=ahar-6cbad
- Metrics available:
  - Request count
  - Request latency (p50, p95, p99)
  - Container CPU utilization
  - Container memory utilization
  - Billable container time
  - Error rate

**Firebase Console:**
- URL: https://console.firebase.google.com/project/ahar-6cbad
- Metrics:
  - Bandwidth usage
  - Request count by country
  - Most requested files

### Cost Monitoring

**Cloud Run:**
- Free tier: 2 million requests/month
- Scales to zero when idle (no cost)
- Cost factors: requests, CPU time, memory, network egress

**Firebase Hosting:**
- Free tier: 10 GB storage, 360 MB/day transfer
- Current usage: ~18 files, minimal bandwidth

**MongoDB Atlas:**
- Free tier: M0 cluster (512 MB storage)
- No cost for current usage

**Claude API:**
- Usage-based pricing (input/output tokens)
- Monitor via Anthropic Console

---

## Troubleshooting

### Backend Won't Start

**Check logs:**
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend" --limit 10 --format="value(timestamp,textPayload)"
```

**Common issues:**
- MongoDB connection failure - check `MONGODB_URI`
- Missing environment variable - check all required vars
- Port mismatch - ensure `PORT=8080` or use `${PORT:-8080}`

### Frontend Can't Reach Backend

**Check CORS:**
```bash
curl -X OPTIONS https://ahar-backend-weym6v5qna-el.a.run.app/api/v1/auth/me \
  -H "Origin: https://ahar-6cbad.web.app" \
  -H "Access-Control-Request-Method: GET" \
  -i | grep -E "access-control"
```

**Should see:**
```
access-control-allow-origin: https://ahar-6cbad.web.app
access-control-allow-credentials: true
```

**If missing, update:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "FRONTEND_URL=https://ahar-6cbad.web.app"
```

### Session Cookie Issues

**Symptoms:**
- User can register/login but gets 401 on subsequent requests
- Chatbot returns "Not authenticated"

**Check browser DevTools:**
1. Open DevTools → Application → Cookies
2. Look for `session_token` cookie
3. Verify `Secure`, `HttpOnly`, `SameSite=None`

**Fix:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "SESSION_COOKIE_SAMESITE=none,SESSION_COOKIE_SECURE=true"
```

### MongoDB Connection Timeout

**Error:** `ServerSelectionTimeoutError`

**Check:**
1. MongoDB Atlas Network Access allows `0.0.0.0/0`
2. `MONGODB_URI` is correct and URL-encoded
3. MongoDB cluster is running (not paused)
4. `certifi` package is installed

**Test connection:**
```bash
# From local machine with backend .env
cd backend
python -c "from pymongo import MongoClient; import certifi; client = MongoClient('YOUR_MONGODB_URI', tlsCAFile=certifi.where()); print(client.admin.command('ping'))"
```

### Deployment Fails

**Cloud Build timeout:**
- Increase timeout: `--timeout=20m`
- Check Docker image size (should be <1GB)

**Permission denied:**
```bash
# Ensure service account has roles
gcloud projects add-iam-policy-binding ahar-6cbad \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
  --role="roles/run.admin"
```

### Frontend Shows Old Version

**Solution:**
1. Clear browser cache (hard refresh)
2. Check deployed version:
   ```bash
   curl -I https://ahar-6cbad.web.app | grep -E "cache|etag"
   ```
3. Force new deployment:
   ```bash
   firebase deploy --only hosting --force
   ```

---

## Updating the Deployment

### Backend Code Changes

```bash
# Make code changes
cd backend

# Deploy (Cloud Build rebuilds automatically)
./deploy-backend.sh

# Or manually
gcloud run deploy ahar-backend \
  --source . \
  --region asia-south1
```

### Frontend Code Changes

```bash
# Make code changes
cd frontend

# Rebuild and deploy
npm run build
firebase deploy --only hosting
```

### Environment Variable Changes

**Backend:**
```bash
# Update single variable
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "KEY=VALUE"

# Update multiple variables
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "KEY1=VALUE1,KEY2=VALUE2"

# Remove variable
gcloud run services update ahar-backend \
  --region asia-south1 \
  --remove-env-vars "KEY"
```

**Frontend:**
```bash
# Edit .env.production
cd frontend
nano .env.production

# Rebuild and redeploy
npm run build
firebase deploy --only hosting
```

---

## Access & Management

### Google Cloud Console
- **URL:** https://console.cloud.google.com/run?project=ahar-6cbad
- **Manage:** Service configuration, logs, metrics, environment variables

### Firebase Console
- **URL:** https://console.firebase.google.com/project/ahar-6cbad
- **Manage:** Hosting, usage, domain settings

### MongoDB Atlas Console
- **URL:** https://cloud.mongodb.com
- **Manage:** Database, network access, users, backups

### Anthropic Console
- **URL:** https://console.anthropic.com
- **Manage:** API keys, usage, billing

---

## Performance Optimization

### Current Configuration
- **Backend:** 2 vCPU, 2 GiB RAM - suitable for moderate traffic
- **Frontend:** Global CDN - fast worldwide
- **Database:** Mumbai region - low latency for Indian users

### Scaling Considerations

**Increase resources:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --memory 4Gi \
  --cpu 4
```

**Adjust scaling:**
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --min-instances 1 \  # Keep warm (avoids cold starts)
  --max-instances 50 \  # Handle traffic spikes
  --concurrency 100      # Requests per container
```

**Cold start optimization:**
- Current: ~3-5 seconds cold start
- Solution: Set `--min-instances 1` (always-on, costs ~$5-10/month)

---

## Backup & Recovery

### Database Backups

**MongoDB Atlas:**
- Automatic snapshots (M0 free tier: limited)
- Upgrade to M10+ for automated backups and point-in-time recovery

**Manual export:**
```bash
# Requires mongodump tool
mongodump --uri="mongodb+srv://ahar_admin:PASSWORD@cluster0.mfk2cuq.mongodb.net/ahar_pos" --out=backup/
```

### Code Backups

- Source code in Git repository
- Firebase Hosting versions retained (rollback available)
- Cloud Run revisions retained (rollback available)

### Rollback Procedures

**Backend:**
```bash
# List revisions
gcloud run revisions list --service ahar-backend --region asia-south1

# Rollback to previous revision
gcloud run services update-traffic ahar-backend \
  --region asia-south1 \
  --to-revisions REVISION_NAME=100
```

**Frontend:**
```bash
# List hosting releases
firebase hosting:releases:list

# Rollback to previous release
firebase hosting:rollback
```

---

## Future Improvements

### Security Enhancements
- [ ] Implement rate limiting middleware
- [ ] Add API request logging and monitoring
- [ ] Migrate secrets to Google Secret Manager
- [ ] Implement static IP with VPC + Cloud NAT for MongoDB IP whitelisting
- [ ] Add Content Security Policy (CSP) headers

### Performance
- [ ] Enable Cloud CDN for backend API (for cacheable endpoints)
- [ ] Implement Redis for session storage (faster than MongoDB)
- [ ] Add database indexes for frequently queried fields
- [ ] Optimize Docker image size (multi-stage builds)

### Monitoring
- [ ] Set up Cloud Monitoring alerts (error rate, latency)
- [ ] Implement structured logging (JSON format)
- [ ] Add application performance monitoring (APM)
- [ ] Set up uptime monitoring and status page

### Cost Optimization
- [ ] Review and optimize Claude API usage
- [ ] Consider reserved instances for predictable load
- [ ] Implement caching for expensive operations
- [ ] Archive old data to reduce database size

---

## Conclusion

The Ahar.AI production deployment is complete and operational:

✅ **Backend** deployed on Google Cloud Run (serverless, scalable)
✅ **Frontend** deployed on Firebase Hosting (global CDN)
✅ **Database** on MongoDB Atlas (cloud-managed)
✅ **SSL/TLS** enabled for all connections
✅ **CORS** configured for cross-origin requests
✅ **Sessions** working with secure cookies
✅ **AI Features** enabled with Claude API

**Live URLs:**
- **Frontend:** https://ahar-6cbad.web.app
- **Backend API:** https://ahar-backend-weym6v5qna-el.a.run.app
- **API Docs:** https://ahar-backend-weym6v5qna-el.a.run.app/docs

The system is production-ready and can handle real user traffic.

---

**Document Maintained By:** Claude Code
**Contact:** See project README for support information
