# OA Gait Analysis — Early Osteoarthritis Detection System

A **local, offline-capable** gait analysis and video screening module for early Osteoarthritis (OA) detection. Built with **MediaPipe Pose**, **OpenCV**, and **SQLite** — runs entirely on your machine without any cloud dependency.

**Version:** 1.0 (Production-Ready — CareSetu)

---

## System Architecture

```
Camera / Video File
       │
       ▼
AlignmentValidator ── pre-recording position guidance (with 5s auto-bypass)
       │
       ▼
  PoseEstimator   ── MediaPipe Pose (33-landmark skeleton)
       │
       ▼
  GaitProcessor   ── Kinematic metrics (knee ROM, hip sway, stride CV …)
       │
       ▼
OARiskClassifier  ── Weighted rule-based scoring vs. clinical norms
       │
       ▼
DatabaseManager   ── SQLite local storage (data/gait_records.db)
       │
       ▼
 GaitDashboard    ── OpenCV HUD / summary screen / history viewer
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.9, 3.10, or 3.11 ⚠️ (NOT 3.13) |
| Webcam | Any standard USB / built-in webcam |
| OS | Windows 10/11, macOS 12+, Ubuntu 20.04+ |

> **All model files are bundled inside the `mediapipe` pip package.  
> No internet connection is needed at runtime after initial install.**

---

## Setup

### 1. Create a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `mediapipe` — pose estimation (includes TFLite models, fully offline at runtime)
- `opencv-python` — video capture & HUD rendering
- `numpy` — joint angle computation

---

## Running the System

### Live Webcam Screening (default)

```bash
python main.py
```

Or with explicit options:

```bash
python main.py --mode screen --camera 0
```

**Session flow:**

1. **Alignment phase** — A guidance overlay appears. Step into frame so your full body is visible. The system checks distance, centring, and landmark visibility.
   - If stuck on the same issue for ≥5 seconds, an **auto-bypass option** appears: `"Step back to show full legs, or press S to skip alignment"`
   - Press `S` to skip alignment or wait for the auto-bypass countdown.

2. **Countdown** — 3-second countdown (press `S` to skip alignment check).

3. **Recording** — Walk naturally across the frame for 10–15 seconds. Knee angles, sway, and step timing are computed in real time and displayed on the live HUD.

4. **Summary** — A full-frame risk assessment is displayed and saved to the database.

**Controls during recording:**

| Key | Action |
|---|---|
| `Q` / `ESC` | End recording & compute results |
| `S` | Skip alignment check (alignment phase only) |

---

### Analyse a Pre-Recorded Video

```bash
python main.py --mode file --input walk.mp4
```

Alignment validation is skipped; analysis starts immediately from frame 1.

---

### Browse Session History

```bash
python main.py --mode history
```

Displays a table of all past sessions (terminal + OpenCV window), including risk level, score, step count, and cadence.

---

### Additional Options

```bash
# Low-spec machine — use MediaPipe Lite model (faster, slightly less accurate)
python main.py --model-complexity 0

# Use a specific webcam (e.g. second camera)
python main.py --camera 1

# Use a custom database location
python main.py --db /path/to/my_sessions.db
```

---

## Camera Positioning Guide

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Side-facing view (preferred for knee flexion ROM):    │
│                                                         │
│    Camera ──────────────────── 2–3 m ──────── Subject   │
│    (fixed)                                  (walking    │
│                                              sideways)  │
│                                                         │
│   OR                                                    │
│                                                         │
│   Front-facing view (preferred for hip sway analysis):  │
│                                                         │
│    Subject ──── walks toward/away ──── Camera           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Tips:**
- Mount the camera at **hip-to-waist height** (≈ 0.9–1.1 m from floor).
- Ensure the **full body** (head to ankles) is visible throughout the walk.
- Use a **plain background** to improve pose detection accuracy.
- Ensure **adequate lighting** — avoid backlighting or heavy shadows.
- Subject should walk at **their natural pace** for 10–20 seconds.

---

## Extracted Kinematic Metrics

| Metric | Clinical Normal Range | OA Relevance |
|---|---|---|
| **Knee Flexion ROM** (L & R) | 55°–75° | Restricted ROM is a primary early-OA marker |
| **Knee Angle Asymmetry** | < 8° | Side-to-side offloading suggests joint pain |
| **Hip Sway Asymmetry** | < 15% of hip width | Abductor weakness / valgus collapse |
| **Stride Timing CV** | < 3% | Irregular rhythm indicates antalgic gait |
| **Stance Phase Ratio** (L & R) | 60%–65% | Altered weight-bearing timing |
| **Cadence** | 90–130 spm | Overall gait speed indicator |

---

## Risk Classification

The classifier applies a **weighted point accumulation** algorithm:

| Points | Risk Level | Colour |
|---|---|---|
| 0–2 | 🟢 **Low Risk** | Green |
| 3–5 | 🟡 **Moderate — Monitor Closely** | Amber |
| 6+ | 🔴 **High Risk / Potential OA Indicator** | Red |

Each metric is compared against published clinical norms (Winter 2009; Kadaba et al. 1990; Mündermann et al. 2005). Deviations award 1–2 penalty points per marker.

> ⚠️ **This system is a screening aid only. It does not constitute a clinical diagnosis. All high/moderate results must be followed up with a qualified orthopaedic or physiotherapy specialist.**

---

## Database

All results are stored locally in `data/gait_records.db` (SQLite, auto-created on first run).

**Tables:**

| Table | Contents |
|---|---|
| `screening_sessions` | Session ID, timestamp, mode, risk level, score, summary |
| `gait_metrics` | Per-session kinematic values (FK → screening_sessions) |

You can query the database directly:

```bash
# Windows / macOS / Linux
sqlite3 data/gait_records.db

sqlite> SELECT id, timestamp, risk_level, risk_score FROM screening_sessions ORDER BY id DESC LIMIT 10;
sqlite> SELECT * FROM gait_metrics WHERE session_id = 5;
```

---

## Project Structure

```
oa_gait_analysis/
├── main.py                  # Entry point & CLI
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── DEPLOYMENT_CHECKLIST.md  # Pre-deployment verification steps
├── PLATFORM_DIFFERENCES.md  # Python vs React Native schema differences
│
├── core/
│   ├── __init__.py
│   ├── camera.py            # CameraInterface + AlignmentValidator (with 5s auto-bypass)
│   ├── pose_estimator.py    # MediaPipe Pose wrapper (with mock fallback)
│   ├── gait_processor.py    # Kinematic metric extraction (fixed cadence calc)
│   ├── oa_classifier.py     # OA risk scoring & classification
│   └── database.py          # SQLite database manager
│
├── ui/
│   ├── __init__.py
│   └── dashboard.py         # OpenCV HUD & history viewer
│
├── data/
│   └── gait_records.db      # Auto-created SQLite database
│
└── mobile/                  # React Native companion app (separate, v1.1)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Cannot open camera/video source: 0` | Try `--camera 1` or check webcam USB connection |
| `No module named mediapipe` | Run `pip install -r requirements.txt` in the activated `.venv` |
| `ModuleNotFoundError: No module named 'cv2'` | Run `pip install -r requirements.txt` and verify pip is in the right venv |
| Pose not detected | Improve lighting; ensure full body is in frame; step back a bit |
| Low FPS / lag | Use `--model-complexity 0` (MediaPipe Lite) for lower-spec machines |
| Database locked | Ensure no other instance is running; restart the script |
| Alignment stuck on "No person detected" | Press `S` to skip alignment. If stuck after 5 seconds, auto-bypass message appears. |
| **Python 3.13 warning about MediaPipe** | Use Python 3.9, 3.10, or 3.11 instead. MediaPipe doesn't yet have official 3.13 support. |

### MediaPipe Not Available (Python 3.13)

If you're on Python 3.13 and see:

```
[WARN] mediapipe.solutions.pose unavailable on this Python build.
       Pose estimation will run in MOCK mode — no skeleton / angles.
```

**Fix:**

1. Install Python 3.11: https://www.python.org/downloads/
2. Create a new venv with Python 3.11:
   ```bash
   /path/to/python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Or, upgrade MediaPipe when 3.13 support lands:
   ```bash
   pip install --upgrade 'mediapipe>=0.11.0'
   ```

---

## What's New in v1.0

✅ **5-second auto-bypass for stuck alignment** — If you can't fit your full body in frame, after 5 seconds the system offers an auto-bypass option instead of trapping you.

✅ **Fixed cadence calculation** — Cadence now counts steps/minute correctly (not stride-based), matching clinical norms.

✅ **Real-time live metrics** — Knee angles, hip sway, and cadence are computed on every frame and displayed live (not fabricated).

✅ **Robust NaN/division-by-zero handling** — All metrics return clean floats; no crashes on edge cases.

✅ **Schema versioning foundation** — Database is prepared for safe migrations in future versions.

✅ **Production-grade error messages** — Clear, actionable troubleshooting guidance if something goes wrong.

---

## Clinical References

1. Winter, D.A. (2009). *Biomechanics and Motor Control of Human Movement* (4th ed.). Wiley.
2. Kadaba, M.P. et al. (1990). Measurement of lower extremity kinematics during level walking. *Journal of Orthopaedic Research*, 8(3), 383–392.
3. Mündermann, A. et al. (2005). Implications of increased medial compartment loading for implant design in total knee arthroplasty. *Osteoarthritis and Cartilage*, 13(8), 699–704.

---

*Built with MediaPipe · OpenCV · NumPy · SQLite — 100% offline capable.*  
*CareSetu v1.0 — Production-Ready Early OA Detection*
