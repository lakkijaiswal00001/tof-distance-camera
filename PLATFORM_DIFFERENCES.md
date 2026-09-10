# Platform Differences: Python Desktop vs React Native Mobile

## Overview

The CareSetu Early OA Detection System has **two independent implementations**:
- **Python Desktop**: `core/`, `ui/`, `main.py` — production-ready gait analysis engine
- **React Native Mobile**: `mobile/` — cross-platform companion app with simulated sensor data

This document outlines the differences and a roadmap to eventual unification.

---

## Database Schema Divergence

### Risk Level Enum Strings

| Component | Values |
|---|---|
| **Python** (`core/oa_classifier.py:41-43`) | `"Low Risk"` / `"Moderate — Monitor Closely"` / `"High Risk / Potential OA Indicator"` |
| **React Native** (`mobile/src/types/index.ts:7`) | `"Low Risk"` / `"Moderate — Monitor"` / `"High Risk / Potential OA"` |

**Issue:** String literals don't match, preventing direct data transfer between platforms.

### Database Locations

| Platform | Path | Format |
|---|---|---|
| Python | `data/gait_records.db` | SQLite 3 |
| Mobile | `oa_gait.db` (AsyncStorage) | JSON objects (simulated) |

### Column Differences

| Column | Python | Mobile | Notes |
|---|---|---|---|
| `session_id` / `id` | ✅ | ✅ | PK, auto-increment |
| `timestamp` | ✅ | ✅ | ISO-8601 |
| `mode` | ✅ | ❌ | `"webcam"` or `"file"` |
| `duration_seconds` | ✅ | ❌ | Recording length in seconds |
| `risk_level` | ✅ | ✅ | Enum string (mismatched) |
| `risk_score` | ✅ | ✅ | 0–12 range |
| `data_sufficient` | ✅ | ❌ | Boolean flag for validity |
| `summary` | ✅ | ✅ | Human-readable assessment |
| `frame_count` | ✅ | ❌ | Frames captured |
| `step_count` | ✅ | ❌ | Heel-strike count |
| `left_knee_rom` | ✅ | ✅ | Range of motion (degrees) |
| `right_knee_rom` | ✅ | ✅ | Range of motion (degrees) |
| `knee_angle_asymmetry` | ✅ | ✅ | L/R asymmetry (degrees) |
| `hip_sway_asymmetry_pct` | ✅ | ✅ | Lateral sway (% of hip width) |
| `stride_duration_mean` | ✅ | ✅ | Mean stride time (seconds) |
| `stride_duration_cv` | ✅ | ✅ | Stride variability (%) |
| `cadence_spm` | ✅ | ✅ | Steps per minute |
| `left_stance_ratio` | ✅ | ✅ | Stance phase ratio (0–1) |
| `right_stance_ratio` | ✅ | ✅ | Stance phase ratio (0–1) |
| **Pressure-based (Mobile only)** | | | |
| `left_pressure_asymmetry_pct` | ❌ | ✅ | FSR asymmetry (simulated) |
| `right_pressure_asymmetry_pct` | ❌ | ✅ | FSR asymmetry (simulated) |
| `pressure_distribution_balance` | ❌ | ✅ | Overall pressure symmetry (%) |

---

## Classifier Thresholds

Both platforms use **identical scoring logic**, with one exception:

### Mobile Pressure-Based Scoring (Python has no equivalent)

```typescript
// mobile/src/services/gaitAnalyzer.ts

const pressureAsymThreshold15 = 15;  // mild warning
const pressureAsymThreshold25 = 25;  // severe

if (abs(left_pressure_asym - right_pressure_asym) > pressureAsymThreshold25) {
    score += 2;  // severe pressure asymmetry
}
```

**Python fallback:** When pressure sensors unavailable, these metrics default to 0.0 (no penalty).

---

## Sensor Data Differences

### Python Desktop

- **Source:** MediaPipe Pose (33-point skeleton from RGB webcam)
- **Data:** Joint angles, hip sway, stride timing from video analysis
- **Real-time:** Yes (30 fps webcam feed)
- **Ground truth:** Actual video — **no simulation**

### React Native Mobile

- **Source:** Simulated sensor streams (generated in `mobile/src/services/sensorService.ts`)
- **Data:** Pressure (FSR), IMU (accelerometer/gyro), optional video
- **Real-time:** Yes (30 fps simulated data)
- **Ground truth:** Three profiles:
  - `normal` — healthy gait characteristics
  - `mild_oa` — subtle deviations
  - `severe_oa` — pronounced markers
- **Note:** Currently **no actual sensor hardware integration**; all data is synthetic

---

## Risk Classification Outputs

Both platforms produce identical risk levels:

| Score | Python | Mobile | Colour (BGR) |
|---|---|---|---|
| 0–2 | `LOW_RISK` | `Low Risk` | Green (0, 200, 80) |
| 3–5 | `MODERATE` | `Moderate — Monitor` | Amber (0, 180, 240) |
| 6+ | `HIGH_RISK` | `High Risk / Potential OA` | Red (30, 40, 220) |

---

## Future Unification Roadmap

### Phase 1: Schema Alignment (CareSetu v1.1)

1. **Standardize risk-level strings:**
   - Choose one canonical enum (recommend `"Low Risk"`, `"Moderate"`, `"High Risk"`)
   - Update both Python and TypeScript

2. **Add schema versioning to mobile:**
   - Migrate from AsyncStorage JSON to SQLite
   - Implement schema version tracking (matching Python's `_ensure_schema_current()`)

3. **Extend Python to support pressure metrics:**
   - Add optional columns for FSR data (when sensor hardware integrated)
   - Update classifier to score pressure asymmetry if available

### Phase 2: Data Sync (CareSetu v1.2)

1. **Implement cloud sync layer:**
   - Option to upload sessions to a shared backend (Firebase, custom server)
   - End-to-end encrypted transmission

2. **Cross-platform history browser:**
   - Unified dashboard showing sessions from both platforms
   - Sync status indicator

### Phase 3: Unified Sensor Integration (CareSetu v2.0)

1. **Pressure sensor hardware:**
   - Integrate real FSR sensors (phone + wearable)
   - Replace simulation with actual data

2. **Shared algorithm:**
   - Single classifier implementation (TypeScript compiled to both platforms via WASM or shared library)
   - Eliminates drift between implementations

---

## Testing Strategy

### Current (v1.0 — Desktop-Only)

- Python: real video + pose estimation
- Mobile: simulated data only
- **No cross-platform testing required**

### Post-Phase 1

- Python: real video + optional pressure
- Mobile: simulated data + SQLite backend
- **Equivalence testing:** Run same subject through both pipelines, compare risk scores

### Post-Phase 2

- Both platforms sync to shared backend
- **Round-trip testing:** Record on desktop → upload → download on mobile → verify metrics match

---

## Known Bugs (To Fix Before Unification)

| Component | Issue | Fix | Priority |
|---|---|---|---|
| Mobile `OfflineIndicator.tsx:10` | Pulse animation recreated on every render | Use `useRef` instead of creating `Animated.Value` on each render | HIGH |
| Mobile `sensorService.ts:82` | Dead ternary branch (both arms return `'stance'`) | Implement proper swing/stance detection logic | HIGH |
| Mobile `gaitAnalyzer.ts:163` | Stride CV computed from knee angle, not stride timing | Recompute from step intervals (match Python) | HIGH |
| Mobile `CameraScreen.tsx:44-57` | Alignment simulated on 700ms timer | Integrate real pose detection when phone camera enabled | MEDIUM |
| Python/Mobile | Risk-level string mismatch | Standardize on single enum | HIGH |

---

## Deployment Checklist

- [ ] Risk-level strings unified
- [ ] Mobile schema versioning implemented
- [ ] Python pressure metrics columns added
- [ ] Mobile bugs fixed
- [ ] Equivalence tests passing
- [ ] Documentation updated with shared classifier reference
- [ ] Version bumped to v1.1

