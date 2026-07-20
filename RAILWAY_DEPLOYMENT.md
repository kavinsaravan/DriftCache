# Railway Deployment Guide

## Why Railway?
- **$5/month free credit** (usually enough for hobby projects)
- **Better free tier**: More RAM than Render's 512MB
- **Built-in PostgreSQL + Redis**
- **Shell access included**
- **Similar workflow to Render**

## Step-by-Step Deployment

### 1. Create Railway Account
1. Go to https://railway.app
2. Sign up with GitHub
3. Authorize Railway to access your repositories

### 2. Create New Project
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose **`DriftCache`** repository
4. Railway will auto-detect the backend

### 3. Add PostgreSQL Database
1. In your project, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway automatically creates a `DATABASE_URL` environment variable
3. No manual configuration needed!

### 4. Add Redis
1. Click **"New"** → **"Database"** → **"Add Redis"**
2. Railway automatically creates a `REDIS_URL` environment variable
3. Done!

### 5. Set Environment Variables
Click on your backend service → **"Variables"** tab → Add:

```
OPENAI_API_KEY=sk-...
SIMILARITY_THRESHOLD=0.90
CACHE_TTL_SECONDS=3600
VERCEL_DOMAIN=drift-cache-jfin.vercel.app
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

**Important**: You do NOT need to set `DATABASE_URL` or `REDIS_URL` - Railway sets these automatically!

### 6. Deploy
1. Railway will auto-deploy on push to `main`
2. Wait for build to complete (~3-5 minutes)
3. Check logs for "Database migrations completed successfully"

### 7. Get Your URL
1. Go to **"Settings"** tab
2. Under **"Domains"**, click **"Generate Domain"**
3. You'll get a URL like: `driftcache-api.up.railway.app`

### 8. Update Frontend
Update `/Users/kavins/Projects/DriftCache/frontend/.env.production`:
```
VITE_API_URL=https://your-app.up.railway.app
```

Then push to trigger Vercel redeploy.

### 9. Test
```bash
curl https://your-app.up.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "llm": "configured"
}
```

### 10. Monitor Usage
- Go to **"Metrics"** tab to see RAM/CPU usage
- Free tier gives $5/month credit
- If you run out, it's still cheaper than Render Standard ($25)

## Troubleshooting

### Out of Memory
If you still get OOM errors:
1. Click **"Settings"** → **"Resources"**
2. Increase RAM allocation (uses more credits)

### Database Connection Issues
Railway auto-injects `DATABASE_URL` - your code already handles this in `config.py`

### Redis Connection Issues
Railway auto-injects `REDIS_URL` - your code already handles this in `redis.py`

### Migration Errors
Check logs - migrations run automatically on startup via `main.py`

## Cost Estimate
- Free tier: $5/month credit
- Typical usage for hobby project: $3-4/month
- Way cheaper than Render Standard ($25/month)
