# CareSetu v1.0 Deployment Checklist

**System:** OA Gait Analysis — Early Osteoarthritis Detection  
**Version:** 1.0 (Production-Ready)  
**Release Date:** 2026-09-10  
**Responsible:** AI/Computer Vision Engineer

---

## Pre-Deployment Verification

### 1. Environment Setup

- [ ] Python 3.9, 3.10, or 3.11 confirmed (NOT 3.13)
- [ ] Fresh `.venv` created: `python -m venv .venv`
- [ ] Virtual environment activated
- [ ] Pip upgraded: `pip install --upgrade pip setuptools wheel`
- [ ] Dependencies installed: `pip install -r requirements.txt` **completes without errors**
- [ ] All packages at pinned versions:
  - `mediapipe==0.10.8`
  - `opencv-python==4.8.1.78`
  - `numpy==1.24.3`

### 2. Import Smoke Test

```bash
python -c "from core import *; from ui import *; print('✅ All imports successful')"
```

- [ ] No import errors
- [ ] No dependency warnings in console

### 3. Mock-Mode Graceful Degradation

**Test with broken MediaPipe:**

```bash
# Temporarily rename mediapipe to trigger fallback
mv .venv/Lib/site-packages/mediapipe .venv/Lib/site-packages/mediapipe.bak
python main.py --mode history  # Should not crash
```

- [ ] Clear warning printed: `"MediaPipe Pose unavailable on this Python build"`
- [ ] System does not crash
- [ ] `estimator.is_mock == True`
- [ ] Restore mediapipe: `mv .venv/Lib/site-packages/mediapipe.bak .venv/Lib/site-packages/mediapipe`

### 4. Database Initialization

```bash
rm -f data/gait_records.db
python main.py --mode history
```

- [ ] `data/gait_records.db` auto-created
- [ ] Schema tables exist: `screening_sessions` and `gait_metrics`
- [ ] Terminal shows: `"No sessions recorded yet"`
- [ ] No SQLite errors

### 5. End-to-End Webcam Session

**Run live screening:**

```bash
python main.py --mode screen --camera 0
```

**Manual Test Steps:**

1. **Alignment Phase (10–15 seconds):**
   - [ ] Alignment guidance overlay appears
   - [ ] Countdown timer visible
   - [ ] Status bar shows: `"ALIGNMENT CHECK"`
   - [ ] Border colour changes based on status (green when READY)
   - [ ] After ~5 seconds of misalignment, `AUTO_BYPASS_TIMEOUT` message appears with countdown
   - [ ] Pressing `S` skips to countdown

2. **Countdown Phase (3 seconds):**
   - [ ] Large countdown digits visible (3, 2, 1)
   - [ ] "Recording will start now" message appears
   - [ ] Automatically transitions to recording

3. **Recording Phase (10–15 seconds):**
   - [ ] Live metrics panel shows:
     - ✅ Left/Right knee angles (real values, not 0)
     - ✅ Knee asymmetry (not fabricated)
     - ✅ Hip sway % (not 0.0)
     - ✅ Cadence in steps/minute (reasonable range: 70–120 spm)
     - ✅ Step count increasing in real-time
   - [ ] Skeleton overlay drawn on frame
   - [ ] Recording timer counts up (MM:SS format)
   - [ ] Pressing `Q` stops recording gracefully

4. **Analysis & Summary Phase:**
   - [ ] Session saved to database (session ID printed)
   - [ ] Risk level displayed: `"Low Risk"` / `"Moderate — Monitor Closely"` / or `"High Risk"`
   - [ ] Risk score: 0–12
   - [ ] Summary metrics table shows all 8 metrics with values
   - [ ] Flagged markers (if any) highlighted in red
   - [ ] Database query confirms session persists:
     ```bash
     sqlite3 data/gait_records.db "SELECT id, timestamp, risk_level, risk_score FROM screening_sessions;"
     ```

### 6. Metrics Validation

**During a 10-second recording walk, verify:**

- [ ] **Knee ROM (L & R):** 50°–75° (normal gait)
- [ ] **Knee Asymmetry:** < 10° (symmetric walk)
- [ ] **Hip Sway %:** < 15% (minimal lateral motion)
- [ ] **Stride CV %:** < 5% (regular cadence)
- [ ] **Cadence:** 80–120 steps/minute (typical walk)
- [ ] **Stance Ratios (L & R):** 60–65% each (normal weight distribution)
- [ ] **All metrics are floats, no NaN or inf:**
  ```bash
  sqlite3 data/gait_records.db "SELECT * FROM gait_metrics ORDER BY id DESC LIMIT 1;" | grep -i nan
  # Should return no output (grep finds nothing)
  ```

### 7. Error Handling — Edge Cases

#### 7a. No Camera

```bash
python main.py --mode screen --camera 99
```

- [ ] Clear error message: `"Cannot open webcam (index 99)"`
- [ ] Suggests troubleshooting steps (try index 0, check drivers)
- [ ] **Does not crash or hang**

#### 7b. Video File (Offline Mode)

```bash
python main.py --mode file --input tests/sample_walk.mp4
```

*(Requires a sample video; optional for v1.0)*

- [ ] Skips alignment phase
- [ ] Processes video frames at actual FPS
- [ ] Completes without frame-skipping errors

#### 7c. Stuck Alignment (≥5 seconds)

- [ ] Position camera to show only upper body (legs out of frame)
- [ ] Wait 5+ seconds
- [ ] `AUTO_BYPASS_TIMEOUT` status appears
- [ ] Message: `"Step back to show full legs, or press S to skip"`
- [ ] Can press `S` to continue OR wait for auto-bypass to trigger

#### 7d. Short Recording (< 5 seconds)

```
# Start recording, press Q after 2 seconds
```

- [ ] Warning printed: `"[WARN] Recording too short (2.0s). Walk for at least 5 seconds…"`
- [ ] Session still saved to DB
- [ ] Risk assessment: `data_sufficient=False`, risk_level=`"Low Risk"`

### 8. History Browser

```bash
python main.py --mode history
```

- [ ] Terminal table displays all past sessions
- [ ] OpenCV window shows formatted history table
- [ ] Columns: ID, Timestamp, Risk Level, Score, Steps, Cadence
- [ ] Rows alternate background colour (zebra stripe)
- [ ] Pressing `Q` or `ESC` closes window gracefully

### 9. Database Integrity

**After running 3+ sessions:**

```bash
sqlite3 data/gait_records.db
```

```sql
-- Check schema version (if implemented)
SELECT * FROM sqlite_sequence;

-- Verify data constraints
SELECT COUNT(*) FROM screening_sessions;
SELECT COUNT(*) FROM gait_metrics;

-- Confirm foreign keys work
SELECT s.id, m.session_id FROM screening_sessions s 
LEFT JOIN gait_metrics m ON m.session_id = s.id;

-- No orphaned metrics (each should have a session)
SELECT * FROM gait_metrics WHERE session_id NOT IN 
  (SELECT id FROM screening_sessions);
```

- [ ] `screening_sessions` row count = number of recordings
- [ ] `gait_metrics` row count = number of recordings
- [ ] No orphaned metrics found
- [ ] Foreign key constraints maintained

### 10. Cross-Platform Documentation

- [ ] `README.md` updated with:
  - Python version constraint (3.9–3.11, not 3.13)
  - Troubleshooting: "MediaPipe not available" → install steps
  - New `AUTO_BYPASS_TIMEOUT` feature documented
  - Example output for a normal gait session
- [ ] `PLATFORM_DIFFERENCES.md` created and reviewed
- [ ] `DEPLOYMENT_CHECKLIST.md` (this file) in repo
- [ ] Code comments updated (especially in `camera.py` watchdog, `gait_processor.py` cadence fix)

### 11. Performance & Resource Usage

- [ ] Webcam HUD renders at ≥20 fps (no significant lag)
- [ ] CPU usage < 80% during recording (monitor with `top` / Task Manager)
- [ ] Memory usage stable (no memory leaks over 5 sessions)
- [ ] Database file size < 1 MB after 10 sessions

### 12. Accessibility & Usability

- [ ] On-screen messages are clear and actionable
- [ ] Countdown is visible and readable
- [ ] Alignment guidance matches real-time feedback
- [ ] Error messages don't spam console (logged, not printed every frame)
- [ ] All colours meet WCAG AA contrast minimums for critical UI
  - Header text (white) vs dark background ✅
  - Risk badge text vs risk-level colour ✅

---

## Final Sign-Off

### Code Quality

- [ ] No Python syntax errors: `python -m py_compile core/*.py ui/*.py main.py`
- [ ] No import cycles detected manually
- [ ] Docstrings present on all public classes/methods
- [ ] Type hints present where applicable (Python 3.9+ style)

### Security

- [ ] No hardcoded paths outside project root
- [ ] Database uses parameterized queries (no SQL injection vectors)
- [ ] File I/O uses `Path` instead of string concatenation
- [ ] No credentials or API keys in code

### Compatibility

- [ ] Tested on Python 3.9, 3.10, 3.11
- [ ] Works on Windows 10/11, macOS 12+, Ubuntu 20.04+
- [ ] OpenCV handles different webcam resolutions gracefully (fallback to 640×480)

---

## Deployment Instructions

### For End Users

```bash
# 1. Clone or download repo
git clone https://github.com/lakkijaiswal00001/tof-distance-camera.git
cd tof-distance-camera

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# OR
.venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run live screening
python main.py

# 5. Or browse history
python main.py --mode history
```

### For Deployment Servers

```bash
# Use Docker (optional, for containerized deployment)
# Dockerfile example:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py", "--mode", "screen"]
```

---

## Known Limitations (v1.0)

- ⚠️ MediaPipe Pose not officially supported on Python 3.13 (user must use 3.9–3.11)
- ⚠️ Mobile app (`mobile/`) uses simulated sensor data; no hardware integration yet
- ⚠️ No cloud sync; database is local-only
- ⚠️ No multi-language support (English only)
- ⚠️ Webcam calibration is automatic; no manual calibration mode

---

## Post-Deployment

### Monitoring

- [ ] Collect anonymised usage metrics (number of sessions, avg risk level)
- [ ] Monitor error reports (e.g., failed database writes, import errors)
- [ ] Gather user feedback on alignment guidance clarity

### Maintenance

- [ ] Update MediaPipe to 0.11+ when Python 3.13 support lands
- [ ] Pin new dependencies if added to `requirements.txt`
- [ ] Version all schema changes in `database.py`

### Next Release (v1.1)

- [ ] Unify Python/Mobile risk-level strings
- [ ] Add mobile SQLite backend
- [ ] Integrate real pressure sensors (if hardware available)
- [ ] Cloud sync layer (Firebase or custom API)

---

## Sign-Off

**Verified By:** [Your Name / Team]  
**Date:** _______________  
**Approval:** ✅ APPROVED FOR PRODUCTION

---

*For questions or issues, contact: [support email]*
