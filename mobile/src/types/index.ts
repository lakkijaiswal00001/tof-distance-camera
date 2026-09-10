// src/types/index.ts
// ─────────────────────────────────────────────────────────────────────────────
// Shared TypeScript types used across the entire app
// ─────────────────────────────────────────────────────────────────────────────

// ── Risk Level ────────────────────────────────────────────────────────────────
export type RiskLevel = 'Low Risk' | 'Moderate — Monitor' | 'High Risk / Potential OA';

// ── Gait Metrics ─────────────────────────────────────────────────────────────
export interface GaitMetrics {
  // Knee angles (degrees)
  leftKneeAngle: number;
  rightKneeAngle: number;
  kneeAsymmetry: number;   // |left - right|
  leftKneeROM: number;   // range of motion over session
  rightKneeROM: number;

  // Pressure (FSR) — 0–100 normalised scale
  leftFootPressure: number;
  rightFootPressure: number;
  pressureAsymmetry: number; // % deviation

  // Stride
  strideAsymmetry: number; // %
  strideDurationCV: number; // coefficient of variation %
  cadenceSPM: number; // steps per minute

  // Stance
  leftStanceRatio: number; // 0.0–1.0
  rightStanceRatio: number;

  // Hip
  hipSwayAsymmetry: number; // %
}

// ── Live Sensor Frame (BLE/simulated tick) ────────────────────────────────────
export interface SensorFrame {
  timestamp: number;  // ms epoch
  leftKneeAngle: number;
  rightKneeAngle: number;
  leftFootPressure: number;
  rightFootPressure: number;
  hipSwayX: number;  // normalised -1 to 1
  stridePhase: 'swing' | 'stance' | 'unknown';
}

// ── Risk Assessment ───────────────────────────────────────────────────────────
export interface RiskAssessment {
  score: number;
  level: RiskLevel;
  flaggedMarkers: FlaggedMarker[];
  summary: string;
  dataValid: boolean;
}

export interface FlaggedMarker {
  name: string;
  value: number;
  unit: string;
  normalRange: string;
  points: number;
}

// ── Screening Session ─────────────────────────────────────────────────────────
export interface ScreeningSession {
  id: number;
  timestamp: string;   // ISO-8601
  durationSeconds: number;
  mode: 'camera' | 'sensor' | 'combined';
  riskLevel: RiskLevel;
  riskScore: number;
  summary: string;
  dataValid: boolean;
  // Flattened metrics for storage
  metrics: GaitMetrics;
}

// ── Navigation ────────────────────────────────────────────────────────────────
export type RootTabParamList = {
  Home: undefined;
  Camera: undefined;
  Dashboard: undefined;
  History: undefined;
};

export type RootStackParamList = {
  Main: undefined;
  SessionDetail: { sessionId: number };
};
