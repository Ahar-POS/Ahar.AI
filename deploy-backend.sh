#!/bin/bash

# Deploy Backend to Google Cloud Run
# This script builds and deploys the FastAPI backend to Cloud Run

set -e  # Exit on error

PROJECT_ID="ahar-6cbad"
SERVICE_NAME="ahar-backend"
REGION="asia-south1"  # Mumbai region (same as MongoDB Atlas)
PORT=8080

# Required secrets — must be set in the environment before running this script.
# Example:
#   export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/..."
#   export CLAUDE_API_KEY="sk-ant-..."
#   ./deploy-backend.sh
if [ -z "$MONGODB_URI" ]; then
    echo "❌ MONGODB_URI is not set. Export it before running this script."
    exit 1
fi
if [ -z "$CLAUDE_API_KEY" ]; then
    echo "❌ CLAUDE_API_KEY is not set. Export it before running this script."
    exit 1
fi

echo "🚀 Deploying Ahar.AI Backend to Google Cloud Run"
echo "================================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo ""

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "."; then
    echo "❌ Not logged in to gcloud. Please run: gcloud auth login"
    exit 1
fi

# Set project
echo "📋 Setting project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling Cloud Run API..."
gcloud services enable run.googleapis.com --quiet
gcloud services enable containerregistry.googleapis.com --quiet
gcloud services enable cloudbuild.googleapis.com --quiet

# Build and deploy
echo "🏗️  Building and deploying backend..."
cd backend

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port $PORT \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "MONGODB_URI=${MONGODB_URI},CLAUDE_API_KEY=${CLAUDE_API_KEY},DB_NAME=ahar_pos,FRONTEND_URL=https://ahar-6cbad.web.app,DEBUG=false" \
  --quiet

# Get the deployed URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')

echo ""
echo "✅ Backend deployed successfully!"
echo "================================================"
echo ""
echo "🌐 Backend URL: $SERVICE_URL"
echo "🔗 Health check: $SERVICE_URL/api/v1/health"
echo ""
echo "📋 Next steps:"
echo "1. Update frontend API URL:"
echo "   - Create frontend/.env.production with: VITE_API_URL=$SERVICE_URL"
echo "   - Rebuild and redeploy frontend: npm run build && firebase deploy"
echo ""
echo "🎉 Deployment complete!"
