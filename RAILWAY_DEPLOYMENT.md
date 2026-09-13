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

---

## Part 2: Deploy Frontend to Vercel

### Prerequisites

- Vercel account (free tier available at https://vercel.com)
- Backend deployed on Railway (from Part 1)

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
VITE_API_URL=https://your-app.up.railway.app
```

**Note**: Replace with your actual Railway backend URL from Step 7 above.

### Step 4: Deploy

Click **Deploy** and Vercel will:
- Install dependencies from `frontend/package.json`
- Build your Vite + React app
- Deploy to global CDN
- Provide a production URL: `https://your-app.vercel.app`

### Step 5: Update Backend CORS

After deployment, update your backend's CORS settings to allow your Vercel domain:

1. Go to Railway Dashboard → Your Service → Variables
2. Add or update `VERCEL_DOMAIN` with your Vercel domain
3. The CORS configuration in `backend/app/core/config.py` will automatically allow `https://*.vercel.app`

### Step 6: Verify Deployment

Visit your Vercel URL and verify:
- Frontend loads successfully
- Can connect to backend API
- Dashboard displays metrics from the backend

---

## Troubleshooting Frontend

### Build Errors on Vercel

Check Vercel build logs for TypeScript or dependency errors.

**Common fixes**:
- Ensure all dependencies are in `frontend/package.json`
- Verify TypeScript has no errors locally: `npm run build`

### Frontend Can't Connect to Backend

**Check CORS configuration**:
- Verify `VERCEL_DOMAIN` environment variable in Railway
- Ensure backend allows your Vercel domain

**Check API URL**:
- Verify `VITE_API_URL` in Vercel environment variables points to Railway backend
