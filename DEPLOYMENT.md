# DriftCache Deployment Guide

Complete guide for deploying DriftCache backend on Render and frontend on Vercel.

## Architecture

- **Backend**: Render (FastAPI + PostgreSQL + Redis)
- **Frontend**: Vercel (React/Next.js) - *Coming Soon*

---

## Part 1: Deploy Backend to Render

### Prerequisites

- GitHub account with DriftCache repository
- Render account (free tier available at https://render.com)
- OpenAI API key

### Step 1: Connect GitHub to Render

1. Go to https://dashboard.render.com
2. Click **New +** → **Blueprint**
3. Connect your GitHub account
4. Select the `DriftCache` repository

### Step 2: Deploy from Blueprint

Render will automatically detect `render.yaml` and create:
- **Web Service**: `driftcache-api`
- **PostgreSQL Database**: `driftcache-db`

**Note**: Redis must be added manually via the Render Dashboard (see Step 2.5 below).

Click **Apply** to start deployment.

### Step 2.5: Add Redis Manually

After the initial deployment:

1. Go to **New +** → **Redis**
2. Configure:
   - **Name**: `driftcache-redis`
   - **Plan**: Starter ($10/month) or Free (25 MB)
   - **Region**: Oregon (same as other services)
   - **Maxmemory Policy**: `allkeys-lru`
3. Click **Create Redis**
4. Once created, go to your `driftcache-api` service → **Environment**
5. Add these variables using the Redis connection details:
   ```
   REDIS_HOST=<your-redis-hostname>
   REDIS_PORT=<your-redis-port>
   ```
6. Save and redeploy the web service

### Step 3: Configure Environment Variables

After deployment starts, go to your `driftcache-api` service:

1. Navigate to **Environment** tab
2. Add the following secret:

```
OPENAI_API_KEY=your-openai-api-key-here
```

3. Click **Save Changes**

**Note**: DATABASE_URL, REDIS_HOST, and REDIS_PORT are automatically configured from the Blueprint.

### Step 4: Verify Deployment

Once deployment completes, your API will be available at:
```
https://driftcache-api.onrender.com
```

Test the health endpoint:
```bash
curl https://driftcache-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "llm": "configured"
}
```

### Step 5: Test the API

Send a test request:
```bash
curl -X POST https://driftcache-api.onrender.com/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Part 2: Deploy Frontend to Vercel

### Prerequisites

- Vercel account (free tier available at https://vercel.com)
- Backend deployed on Render (from Part 1)

### Step 1: Connect Repository to Vercel

1. Go to https://vercel.com/new
2. Click **Import Git Repository**
3. Select your `DriftCache` repository from GitHub
4. Vercel will detect it as a monorepo

### Step 2: Configure Project Settings

**Important**: Since this is a monorepo, configure the following:

- **Framework Preset**: Vite
- **Root Directory**: `frontend` (click "Edit" and select the frontend folder)
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Install Command**: `npm install`

### Step 3: Configure Environment Variables

Add the backend API URL in the Environment Variables section:

```
VITE_API_URL=https://driftcache-api.onrender.com
```

**Note**: Your backend URL should be the one provided by Render (check your Render dashboard).

### Step 4: Deploy

Click **Deploy** and Vercel will:
- Install dependencies from `frontend/package.json`
- Build your Vite + React app
- Deploy to global CDN
- Provide a production URL: `https://your-app.vercel.app`

### Step 5: Update Backend CORS

After deployment, update your backend's CORS settings to allow your Vercel domain:

1. Go to Render Dashboard → `driftcache-api` → Environment
2. The CORS is already configured to allow `https://*.vercel.app`
3. No changes needed - Vercel domains are pre-configured!

### Step 6: Verify Deployment

Visit your Vercel URL and verify:
- Frontend loads successfully
- Can connect to backend API
- Dashboard displays metrics from the backend

---

## Manual Deployment (Alternative)

If you prefer manual setup without the blueprint:

### 1. Create PostgreSQL Database

```bash
# On Render Dashboard
New + → PostgreSQL
Name: driftcache-db
Plan: Free
```

Save the **Internal Database URL** (starts with `postgresql://`)

### 2. Create Redis Instance

```bash
# On Render Dashboard
New + → Redis
Name: driftcache-redis
Plan: Free
Maxmemory Policy: allkeys-lru
```

Save the **Internal Redis URL**

### 3. Create Web Service

```bash
# On Render Dashboard
New + → Web Service
```

Configure:
- **Runtime**: Python 3
- **Build Command**: `cd backend && pip install -r requirements.txt`
- **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Environment Variables:
```
DATABASE_URL=<your-postgres-internal-url>
REDIS_HOST=<your-redis-host>
REDIS_PORT=<your-redis-port>
OPENAI_API_KEY=<your-openai-key>
PYTHON_VERSION=3.11
ENVIRONMENT=production
```

---

## Monitoring & Maintenance

### Health Checks

Render automatically monitors `/health` endpoint.

### View Logs

```bash
# On Render Dashboard
Your Service → Logs tab
```

### Scale Resources

Free tier limitations:
- Web Service: 512 MB RAM
- PostgreSQL: 1 GB storage
- Redis: 25 MB storage

Upgrade to Starter plan for:
- More RAM and storage
- No sleep after inactivity
- Better performance

### Database Migrations

After deployment, check database tables:

```bash
# Run via Render Shell
Your Service → Shell tab

python -c "from app.database.session import get_db_manager; get_db_manager().create_tables()"
```

---

## API Endpoints Reference

After deployment, your API provides:

### Core Endpoints
- `GET /health` - Health status
- `GET /api/v1/models` - Available models
- `POST /api/v1/chat/completions` - OpenAI-compatible chat

### Monitoring
- `GET /api/v1/metrics/summary` - Cache metrics
- `GET /api/v1/vectorstore/health` - Index health
- `GET /api/v1/vectorstore/status` - Index status

### Management
- `POST /api/v1/drift/run-check` - Drift detection
- `POST /api/v1/evaluation/run` - Cache evaluation
- `POST /api/v1/supervisor/run` - Supervisor orchestration
- `POST /api/v1/vectorstore/rebuild` - Rebuild FAISS index

Full API docs available at:
```
https://driftcache-api.onrender.com/docs
```

---

## Troubleshooting

### Service Won't Start

**Check logs**:
1. Go to Render Dashboard → Your Service → Logs
2. Look for Python errors or missing dependencies

**Common fixes**:
- Ensure `requirements.txt` is in `backend/` directory
- Verify all environment variables are set
- Check DATABASE_URL format is correct

### Database Connection Errors

**Verify DATABASE_URL**:
```bash
# Should start with: postgresql://
# Not: postgres:// (wrong)
```

**Fix**: Update environment variable to use `postgresql://`

### Redis Connection Errors

**Check Redis status**:
1. Go to Render Dashboard → Redis instance
2. Ensure status is "Available"
3. Verify REDIS_HOST and REDIS_PORT match Internal Connection details

### CORS Errors from Frontend

**Update CORS_ORIGINS** in `backend/app/core/config.py`:

```python
CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "https://your-frontend.vercel.app",
]
```

Then redeploy.

---

## Cost Estimation

### Free Tier (Recommended for Development)
- Web Service: Free (sleeps after 15min inactivity)
- PostgreSQL: Free (1 GB, expires after 90 days)
- Redis: Free (25 MB)
- **Total: $0/month**

### Starter Tier (Recommended for Production)
- Web Service: $7/month (512 MB RAM, always on)
- PostgreSQL: $7/month (1 GB, persistent)
- Redis: $10/month (100 MB)
- **Total: $24/month**

### Professional Tier (High Traffic)
- Web Service: $25/month (2 GB RAM, autoscaling)
- PostgreSQL: $20/month (10 GB)
- Redis: $30/month (1 GB)
- **Total: $75/month**

---

## Next Steps

1. ✅ Deploy backend to Render
2. ⏳ Build frontend dashboard (React/Next.js)
3. ⏳ Deploy frontend to Vercel
4. ⏳ Set up custom domain
5. ⏳ Configure monitoring and alerts

---

## Support

- **Documentation**: https://docs.render.com
- **Render Support**: https://render.com/docs/support
- **GitHub Issues**: https://github.com/kavinsaravan/DriftCache/issues

---

**Last Updated**: 2026-06-15
