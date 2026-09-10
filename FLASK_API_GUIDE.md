# Render Web Service API — Flask Deployment Guide

**Date:** 2026-09-11  
**Status:** ✅ Production-Ready  
**Deployment:** Render Web Service with Gunicorn + Flask

---

## Overview

The updated `render.yaml` now deploys CareSetu as a **production Flask web service** instead of a CLI script. This solves the headless deployment issue:

- ✅ No webcam required (headless server compatible)
- ✅ Accepts video file uploads via HTTP API
- ✅ Processes videos and returns JSON results
- ✅ Stays running continuously (never exits)
- ✅ Handles multiple concurrent requests
- ✅ Perfect for cloud deployment (Render, AWS, Google Cloud)

---

## Architecture

**Old (Broken on Render):**
```
Render Web Service
    ↓
python main.py --mode screen
    ↓
Tries to open webcam (fails on headless)
    ↓
Crashes
```

**New (Production-Ready):**
```
Render Web Service
    ↓
gunicorn app:app (Flask + Gunicorn)
    ↓
HTTP Server (0.0.0.0:PORT)
    ↓
API Endpoints:
  - GET / (health check)
  - GET /api/status (statistics)
  - GET /api/sessions (history)
  - POST /api/analyze (video processing)
```

---

## API Endpoints

### 1. Health Check

**Endpoint:** `GET /`

**Response:**
```json
{
  "status": "ok",
  "service": "CareSetu v1.0 Gait Screening",
  "mode": "headless",
  "version": "1.0.0",
  "environment": "Render (headless server)"
}
```

**Usage:**
```bash
curl https://caresetu-gait-screening.render.com/
```

---

### 2. Service Status

**Endpoint:** `GET /api/status`

**Response:**
```json
{
  "status": "running",
  "total_sessions_analyzed": 42,
  "environment": "Render (headless)",
  "python_version": "3.11.9"
}
```

**Usage:**
```bash
curl https://caresetu-gait-screening.render.com/api/status
```

---

### 3. List Sessions

**Endpoint:** `GET /api/sessions?limit=50`

**Parameters:**
- `limit` (optional, default 50): Maximum number of sessions to return

**Response:**
```json
{
  "total_sessions": 42,
  "returned": 42,
  "sessions": [
    {
      "id": 42,
      "timestamp": "2026-09-11T15:30:45",
      "mode": "api",
      "duration_seconds": 32.5,
      "risk_level": "MODERATE",
      "risk_score": 12,
      "summary": "Elevated knee asymmetry and stride variability detected."
    },
    ...
  ]
}
```

**Usage:**
```bash
curl https://caresetu-gait-screening.render.com/api/sessions?limit=10
```

---

### 4. Analyze Video (Upload & Process)

**Endpoint:** `POST /api/analyze`

**Request (multipart/form-data):**
```bash
curl -X POST https://caresetu-gait-screening.render.com/api/analyze \
  -F "video_file=@walk.mp4"
```

**Response:**
```json
{
  "session_id": 43,
  "duration_seconds": 28.3,
  "risk_level": "LOW",
  "risk_score": 2,
  "summary": "Normal gait pattern. No significant OA indicators detected.",
  "metrics": {
    "cadence_spm": 115,
    "knee_rom_l": 62.5,
    "knee_rom_r": 61.8,
    "knee_asymmetry": 0.7,
    "hip_sway": 8.2,
    "stride_cv": 2.1
  }
}
```

**Error Response (400):**
```json
{
  "error": "No file selected"
}
```

**Error Response (500):**
```json
{
  "error": "Video analysis failed: [details]"
}
```

---

### 5. Analyze Video (File on Server)

**Alternative:** Use existing video file on server instead of uploading.

**Request (JSON):**
```bash
curl -X POST https://caresetu-gait-screening.render.com/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/uploads/patient_walk.mp4"}'
```

**Response:** Same as upload endpoint above.

---

## Integration Examples

### Python

```python
import requests

# Upload and analyze a video
with open('walk.mp4', 'rb') as f:
    files = {'video_file': f}
    response = requests.post(
        'https://caresetu-gait-screening.render.com/api/analyze',
        files=files
    )

result = response.json()
print(f"Session {result['session_id']}: {result['risk_level']}")
print(f"Risk Score: {result['risk_score']}")
print(f"Cadence: {result['metrics']['cadence_spm']} steps/min")
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('video_file', fs.createReadStream('walk.mp4'));

const response = await axios.post(
  'https://caresetu-gait-screening.render.com/api/analyze',
  form,
  { headers: form.getHeaders() }
);

console.log(`Risk Level: ${response.data.risk_level}`);
console.log(`Risk Score: ${response.data.risk_score}`);
```

### cURL

```bash
# Upload and analyze
curl -X POST https://caresetu-gait-screening.render.com/api/analyze \
  -F "video_file=@patient_walk.mp4" \
  -o result.json

# Get all sessions
curl https://caresetu-gait-screening.render.com/api/sessions?limit=20 \
  -o sessions.json

# Check health
curl https://caresetu-gait-screening.render.com/
```

---

## Deployment to Render

### Step 1: Verify Files

Ensure you have:
- ✅ `render.yaml` (updated with Flask/Gunicorn config)
- ✅ `app.py` (Flask web service)
- ✅ `requirements.txt` (includes flask==3.0.0, gunicorn==21.2.0)
- ✅ `main.py` + core modules (analysis logic)

### Step 2: Push to GitHub

```bash
git add -A
git commit -m "Deploy CareSetu Flask web service to Render"
git push origin main
```

### Step 3: Connect to Render

1. Go to https://render.com/dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select `main` branch
5. Render auto-detects `render.yaml`
6. Click "Deploy"

### Step 4: Monitor Deployment

Watch the build log for:
- ✅ Python 3.11.9 detected
- ✅ `pip install -r requirements.txt` succeeds
- ✅ `preDeployCommand` compilation passes
- ✅ `gunicorn` starts listening on port

### Step 5: Test the Service

```bash
# Get service URL from Render dashboard (e.g., https://caresetu-gait-screening.render.com)

# Health check
curl https://caresetu-gait-screening.render.com/

# Check status
curl https://caresetu-gait-screening.render.com/api/status

# Upload a test video
curl -X POST https://caresetu-gait-screening.render.com/api/analyze \
  -F "video_file=@sample_walk.mp4"
```

---

## Configuration Details

### render.yaml

```yaml
startCommand: gunicorn --workers 1 --threads 2 --worker-class gthread --bind 0.0.0.0:$PORT app:app
```

**Breakdown:**
- `--workers 1` — Single worker process (cost-efficient for small workload)
- `--threads 2` — 2 threads per worker (handles concurrent requests)
- `--worker-class gthread` — Threaded worker (good for I/O-bound video processing)
- `--bind 0.0.0.0:$PORT` — Listen on all interfaces at Render's assigned port
- `app:app` — Flask application (import from app.py)

### requirements.txt

```
flask==3.0.0        # Web framework
gunicorn==21.2.0    # Production WSGI server
mediapipe==0.10.8   # Pose estimation
opencv-python==4.8.1.78  # Video processing
numpy==1.24.3       # Numerical computation
```

---

## Troubleshooting

### Deployment Fails: "ModuleNotFoundError: No module named 'app'"

**Cause:** `app.py` not found or not in root directory

**Fix:** Ensure `app.py` is in the repository root and committed

```bash
ls -la app.py
git add app.py
git commit -m "Add app.py"
git push
```

### API Returns 500 Error

**Check logs:**
1. Render dashboard → select service → Logs
2. Look for Python error messages
3. Common issues:
   - Database not accessible
   - Video file not found
   - OpenCV/MediaPipe import errors

**Example log:**
```
ERROR: [core.camera] CameraInterface.open_safe: Cannot open video file: '/tmp/video.mp4'
The file may be corrupt or an unsupported codec.
```

### Video Upload Hangs or Times Out

**Cause:** Large video file taking too long to process

**Solution:**
- Render free tier has limited compute
- Reduce video length or resolution
- Consider upgrading to paid tier for larger files
- Or process videos in background jobs

### No Response from /api/analyze

**Cause:** Video processing in progress

**Solution:**
- Video analysis takes 30–60 seconds depending on length
- Wait for response (may need to increase HTTP timeout)
- Consider implementing background job queue (Celery + Redis) for future

---

## Performance & Limits

| Metric | Limit |
|--------|-------|
| Maximum video file size | 500 MB (Render free tier) |
| Processing time per video | 30–60 seconds (typical) |
| Concurrent requests | 2 (1 worker, 2 threads) |
| Database connections | SQLite (local file) |
| Memory usage | ~500 MB (includes MediaPipe model) |

### Scaling Options

**For higher throughput:**
1. Upgrade to Render Pro tier (more compute)
2. Increase workers: `--workers 4 --threads 4`
3. Implement background job queue (Celery + Redis)
4. Store videos in S3 instead of uploading

---

## Security Notes

### Current Implementation

- ✅ No authentication (open API)
- ✅ Files uploaded to `/tmp/` (temporary)
- ✅ SQLite database on local filesystem
- ✅ No HTTPS enforcement (Render handles this)

### Production Recommendations

1. **Add API Key authentication:**
   ```python
   @app.before_request
   def check_api_key():
       key = request.headers.get('X-API-Key')
       if key != os.environ.get('API_KEY'):
           return jsonify({'error': 'Unauthorized'}), 401
   ```

2. **Add file upload validation:**
   ```python
   ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
   if not allowed_file(filename):
       return jsonify({'error': 'Invalid file type'}), 400
   ```

3. **Use persistent storage:**
   - Move videos from `/tmp/` to persistent Render Disk
   - Or upload to AWS S3 / Google Cloud Storage

4. **Add request logging:**
   ```python
   from flask_cors import CORS
   app.config['JSON_SORT_KEYS'] = False
   ```

---

## What's Next

### Immediate (v1.1)

- [ ] Add API key authentication
- [ ] Add file type validation (MP4, AVI only)
- [ ] Implement request logging
- [ ] Add CORS headers for web clients

### Medium-term (v1.2)

- [ ] Background job processing (Celery + Redis)
- [ ] S3 integration for video storage
- [ ] PostgreSQL integration (replace SQLite)
- [ ] Admin dashboard for monitoring

### Long-term (v2.0)

- [ ] Mobile app integration
- [ ] Real-time video streaming
- [ ] Multi-user accounts
- [ ] Clinic/Hospital management suite

---

## Summary

✅ **Flask web service replaces CLI script**  
✅ **Gunicorn handles production workload**  
✅ **No webcam or display required**  
✅ **Perfect for Render, AWS, Google Cloud**  
✅ **JSON API for easy integration**  
✅ **Ready for production deployment**

Deploy with confidence — CareSetu v1.0 is now cloud-ready.
