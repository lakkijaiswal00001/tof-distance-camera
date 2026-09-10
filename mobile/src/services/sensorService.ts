// src/services/sensorService.ts
// ─────────────────────────────────────────────────────────────────────────────
// Simulated FSR + IMU sensor stream (BLE-ready architecture).
//
// In production: replace startSimulation() with a real BLE GATT
// subscription via expo-ble or react-native-ble-plx.
// The SensorFrame interface and callback signature stay identical.
// ─────────────────────────────────────────────────────────────────────────────

import type { SensorFrame } from '../types';

// ── Gaussian noise helper ─────────────────────────────────────────────────────
function gaussian(mean: number, std: number): number {
  // Box-Muller transform
  const u1 = Math.random(), u2 = Math.random();
  const z  = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  return mean + std * z;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

// ── Gait simulation state ─────────────────────────────────────────────────────
type GaitProfile = 'normal' | 'mild_oa' | 'severe_oa';

interface SimState {
  phaseAngle:   number;   // 0 – 2π walking cycle
  profile:      GaitProfile;
  intervalId:   ReturnType<typeof setInterval> | null;
}

const state: SimState = {
  phaseAngle:   0,
  profile:      'normal',
  intervalId:   null,
};

// ── Profile parameters ────────────────────────────────────────────────────────
const PROFILES: Record<GaitProfile, {
  kneeFlexPeak:    number;  // max knee angle degrees
  kneeAsymBias:    number;  // L-R bias degrees
  pressureAsym:    number;  // 0-1 fraction
  hipSway:         number;  // amplitude 0-1
  strideHz:        number;  // steps per second
  noiseScale:      number;
}> = {
  normal: {
    kneeFlexPeak:  65,  kneeAsymBias:  2,
    pressureAsym: 0.05, hipSway:      0.08,
    strideHz:      1.8, noiseScale:   0.8,
  },
  mild_oa: {
    kneeFlexPeak:  48,  kneeAsymBias:  9,
    pressureAsym: 0.18, hipSway:      0.17,
    strideHz:      1.4, noiseScale:   1.5,
  },
  severe_oa: {
    kneeFlexPeak:  38,  kneeAsymBias: 15,
    pressureAsym: 0.28, hipSway:      0.28,
    strideHz:      1.1, noiseScale:   2.5,
  },
};

// ── Frame generator ───────────────────────────────────────────────────────────
function generateFrame(): SensorFrame {
  const p   = PROFILES[state.profile];
  const phi = state.phaseAngle;

  // Knee flexion: sinusoidal over gait cycle
  const kneeBase     = clamp(p.kneeFlexPeak * Math.abs(Math.sin(phi)), 5, 90);
  const leftKneeAngle  = clamp(gaussian(kneeBase,            p.noiseScale), 0, 90);
  const rightKneeAngle = clamp(gaussian(kneeBase + p.kneeAsymBias, p.noiseScale), 0, 90);

  // Foot pressure: alternating between feet
  const swing = (Math.sin(phi) + 1) / 2;  // 0-1 normalized within cycle
  const leftRaw  = clamp(gaussian(swing * 80 + 10,                p.noiseScale * 5), 0, 100);
  const rightRaw = clamp(gaussian((1 - swing) * 80 * (1 - p.pressureAsym) + 10, p.noiseScale * 5), 0, 100);

  // Stride phase
  const stridePhase: SensorFrame['stridePhase'] =
    swing < 0.35 ? 'swing' : swing > 0.65 ? 'stance' : 'stance';

  // Hip sway: lateral oscillation
  const hipSwayX = clamp(gaussian(p.hipSway * Math.sin(phi * 2), p.noiseScale * 0.02), -1, 1);

  return {
    timestamp:        Date.now(),
    leftKneeAngle,
    rightKneeAngle,
    leftFootPressure:  leftRaw,
    rightFootPressure: rightRaw,
    hipSwayX,
    stridePhase,
  };
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Start the simulated sensor stream.
 * @param onFrame  Callback fired every ~33ms (≈30 fps)
 * @param profile  Gait profile to simulate
 */
export function startSensorStream(
  onFrame: (frame: SensorFrame) => void,
  profile: GaitProfile = 'normal',
): void {
  stopSensorStream();
  state.profile    = profile;
  state.phaseAngle = 0;

  const p = PROFILES[profile];
  const dt = 1 / 30;  // 30 fps

  state.intervalId = setInterval(() => {
    state.phaseAngle = (state.phaseAngle + dt * p.strideHz * Math.PI * 2) % (Math.PI * 2);
    onFrame(generateFrame());
  }, 33);
}

/** Stop the sensor stream. */
export function stopSensorStream(): void {
  if (state.intervalId !== null) {
    clearInterval(state.intervalId);
    state.intervalId = null;
  }
}

/** Switch profile while streaming (simulates changing patient/condition). */
export function setSensorProfile(profile: GaitProfile): void {
  state.profile = profile;
}

export type { GaitProfile };
