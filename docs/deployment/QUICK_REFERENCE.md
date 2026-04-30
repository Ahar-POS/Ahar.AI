# Production Deployment - Quick Reference

Quick commands for common production operations.

---

## Deployment Commands

### Deploy Backend
```bash
./deploy-backend.sh
```

### Deploy Frontend
```bash
cd frontend
npm run build
firebase deploy --only hosting
```

---

## Environment Variables

### View Backend Env Vars
```bash
gcloud run services describe ahar-backend \
  --region asia-south1 \
  --format="table(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)"
```

### Update Backend Env Var
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "KEY=VALUE"
```

### Update Multiple Env Vars
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "KEY1=VALUE1,KEY2=VALUE2,KEY3=VALUE3"
```

---

## Current Configuration

### Production URLs
- **Frontend:** https://ahar-6cbad.web.app
- **Backend:** https://ahar-backend-weym6v5qna-el.a.run.app
- **API Docs:** https://ahar-backend-weym6v5qna-el.a.run.app/docs

### Backend Environment Variables
```bash
MONGODB_URI=mongodb+srv://ahar_admin:Ahar%40ATLAS%24%24@cluster0.mfk2cuq.mongodb.net/?appName=Cluster0
DB_NAME=ahar_pos
FRONTEND_URL=https://ahar-6cbad.web.app
DEBUG=false
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=none
CLAUDE_API_KEY=sk-ant-api03-***
```

### Frontend Environment Variables
**File:** `frontend/.env.production`
```bash
VITE_API_URL=https://ahar-backend-weym6v5qna-el.a.run.app
```

---

## Monitoring

### View Logs
```bash
# Recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend" --limit 50

# Errors only
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ahar-backend AND severity>=ERROR" --limit 20

# Stream live logs
gcloud logging tail "resource.labels.service_name=ahar-backend"
```

### Health Check
```bash
curl https://ahar-backend-weym6v5qna-el.a.run.app/api/v1/health
```

### Test CORS
```bash
curl -X OPTIONS https://ahar-backend-weym6v5qna-el.a.run.app/api/v1/auth/me \
  -H "Origin: https://ahar-6cbad.web.app" \
  -H "Access-Control-Request-Method: GET" \
  -i | grep -E "access-control"
```

---

## Service Management

### List Services
```bash
gcloud run services list --region asia-south1
```

### Describe Service
```bash
gcloud run services describe ahar-backend --region asia-south1
```

### List Revisions
```bash
gcloud run revisions list --service ahar-backend --region asia-south1
```

### Rollback to Previous Revision
```bash
gcloud run services update-traffic ahar-backend \
  --region asia-south1 \
  --to-revisions REVISION_NAME=100
```

### Delete Service (Careful!)
```bash
gcloud run services delete ahar-backend --region asia-south1
```

---

## Troubleshooting

### Backend Not Responding
```bash
# Check if service is running
gcloud run services describe ahar-backend --region asia-south1 --format="value(status.conditions)"

# Check recent errors
gcloud logging read "resource.labels.service_name=ahar-backend AND severity>=ERROR" --limit 10
```

### Session Cookie Issues
```bash
# Update cookie settings
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "SESSION_COOKIE_SAMESITE=none,SESSION_COOKIE_SECURE=true"
```

### CORS Issues
```bash
# Update frontend URL
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "FRONTEND_URL=https://ahar-6cbad.web.app"
```

### MongoDB Connection Issues
```bash
# Update MongoDB URI
gcloud run services update ahar-backend \
  --region asia-south1 \
  --update-env-vars "MONGODB_URI=mongodb+srv://..."
```

---

## Console Access

- **Cloud Run:** https://console.cloud.google.com/run?project=ahar-6cbad
- **Firebase:** https://console.firebase.google.com/project/ahar-6cbad
- **MongoDB Atlas:** https://cloud.mongodb.com
- **Anthropic:** https://console.anthropic.com

---

## Common Tasks

### Update Backend Code
```bash
# Make changes, then:
./deploy-backend.sh
```

### Update Frontend Code
```bash
# Make changes, then:
cd frontend
rm -rf dist node_modules/.vite
npm run build
firebase deploy --only hosting
```

### Scale Backend Resources
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --memory 4Gi \
  --cpu 4 \
  --max-instances 20
```

### Keep Backend Always-On (Avoid Cold Starts)
```bash
gcloud run services update ahar-backend \
  --region asia-south1 \
  --min-instances 1
```

---

For detailed information, see [PRODUCTION_SETUP.md](./PRODUCTION_SETUP.md)
