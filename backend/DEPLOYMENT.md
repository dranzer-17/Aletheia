# Deployment Guide for Render

## Pre-Deployment Checklist

### ✅ Changes Made for Production:

1. **MongoDB Connection**: Updated to use MongoDB Atlas cloud database
2. **CORS Configuration**: Now configurable via `ALLOWED_ORIGINS` environment variable
3. **Database Connection**: Fixed hardcoded localhost references in deepfake module
4. **Environment Variables**: Created `.env.example` template
5. **Procfile**: Added for Render deployment
6. **Async Database**: Converted deepfake db_utils to use async motor

## Deployment Steps on Render (Free Tier)

### 1. Create New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select the `Mumbai-Hacks` repository

### 2. Configure Service

**Basic Settings:**
- **Name**: `mumbai-hacks-backend` (or your preferred name)
- **Region**: Choose closest to your users
- **Branch**: `main`
- **Root Directory**: `backend`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. Environment Variables

Add these in the Render dashboard (Environment tab):

```
# Required - MongoDB
MONGO_URI=mongodb+srv://kavish17shah2509_db_user:K17@shah@cluster0.gvz2cyw.mongodb.net/?appName=Cluster0
MONGO_DB=hackathon_db

# Required - Security
SECRET_KEY=9737517a2789d6256701e8ed43dc4e2816a87fe3237d36e4e22aa64bc4f829c6
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# Required - CORS (update with your frontend URL)
ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend-domain.vercel.app

# API Keys - Copy from your .env
GNEWS_API_KEY=your_key
GOOGLE_CLOUD_API_KEY=your_key
LLM_MODEL_NAME=gemini-2.5-flash
FIRECRAWL_API_KEY=your_key
SERPAPI_API_KEY=your_key
TAVILY_API_KEY=your_key
HUGGINGFACE_API_KEY=your_key
ASSEMBLY_AI_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
SIGHTENGINE_API_USER=your_user
SIGHTENGINE_API_SECRET=your_secret
HIVE_API_KEY=your_key
ZEROTRUE_API_KEY=your_key

# Reddit API
REDDIT_USER_AGENT=TrendLens/1.0 by OkIndependent7346
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret

# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Python Version
PYTHON_VERSION=3.13.0
```

### 4. Health Check

- **Health Check Path**: `/`

### 5. Deploy

Click "Create Web Service" and wait for deployment to complete.

## Important Notes for Render Free Tier

### ⚠️ Limitations:

1. **Spin Down**: Service spins down after 15 minutes of inactivity
   - First request after spin down will be slow (30-60 seconds)
   
2. **750 hours/month**: Free tier limit across all services

3. **No Persistent Storage**: 
   - Use MongoDB Atlas for data persistence
   - Uploaded files will be lost on restart
   - Consider using cloud storage (Cloudinary, AWS S3) for file uploads

4. **Memory Limit**: 512 MB RAM
   - Large ML models disabled in deepfake module
   - Consider using external AI APIs instead

### 🔧 Recommended Optimizations:

1. **Keep Alive Service** (Optional):
   ```python
   # Use a cron job or external service to ping your API every 14 minutes
   # to prevent spin down
   ```

2. **Caching**:
   - Use MongoDB for caching trend data (already implemented)
   - Consider Redis for session storage if needed

3. **Background Jobs**:
   - APScheduler is used but will restart on spin down
   - Consider external cron service for critical scheduled tasks

## Post-Deployment

### 1. Update Frontend

Update your frontend's API base URL to:
```javascript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://your-app.onrender.com'
```

### 2. Update CORS

After deploying frontend, update `ALLOWED_ORIGINS` environment variable:
```
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

### 3. Test Endpoints

Test critical endpoints:
- Health check: `https://your-app.onrender.com/`
- Auth: `/auth/signup`, `/auth/login`
- Trends: `/trends/reddit`, `/trends/news`

### 4. Monitor Logs

Check Render logs for any errors:
- Go to your service → "Logs" tab
- Watch for MongoDB connection issues
- Verify scheduler starts correctly

## Troubleshooting

### MongoDB Connection Error

If you see "unable to connect to MongoDB":
- Verify MONGO_URI is correct
- Check MongoDB Atlas network access (allow all IPs: `0.0.0.0/0`)
- Ensure database user exists with correct permissions

### CORS Error

If frontend can't connect:
- Add frontend URL to `ALLOWED_ORIGINS`
- Include both `http://` and `https://` versions
- Check Render logs for CORS-related errors

### Scheduler Not Running

- Scheduler restarts on every deploy/spin down
- Check logs for scheduler initialization messages
- Consider external cron job for critical scheduled tasks

### Module Import Errors

- Ensure all dependencies in `requirements.txt`
- Check Python version compatibility
- Review build logs in Render

## Monitoring

1. **Uptime**: Use [UptimeRobot](https://uptimerobot.com/) to monitor and keep service alive
2. **Logs**: Regularly check Render logs for errors
3. **Performance**: Monitor response times for optimization opportunities

## Cost Optimization

To reduce costs and improve performance:
1. Deploy frontend on Vercel (free)
2. Use MongoDB Atlas free tier (already configured)
3. Consider upgrading to Render paid tier if you need:
   - No spin down
   - More memory/CPU
   - Custom domains
   - Persistent storage

## Getting Your Backend URL

After deployment, your backend will be available at:
```
https://mumbai-hacks-backend-XXXX.onrender.com
```

Copy this URL and use it in your frontend configuration.
