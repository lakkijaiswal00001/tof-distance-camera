// src/services/gaitAnalyzer.ts
// ─────────────────────────────────────────────────────────────────────────────
// TypeScript port of the Python OARiskClassifier.
// Pure function — no side effects, fully offline.
// ─────────────────────────────────────────────────────────────────────────────

import type { GaitMetrics, RiskAssessment, FlaggedMarker, RiskLevel } from '../types';

// ── Clinical normal ranges (matches Python backend) ───────────────────────────
const THRESHOLDS = {
  kneeRomLowWarn:    55,
  kneeRomLowSevere:  50,
  kneeAsymWarn:       8,
  kneeAsymSevere:    12,
  hipSwayWarn:       15,
  hipSwaySevere:     22,
  strideCvWarn:       3,
  strideCvSevere:     6,
  stanceLowWarn:      0.55,
  stanceHighWarn:     0.68,
  pressureAsymWarn:  15,
  pressureAsymSevere:25,
} as const;

function scoreKneeRom(rom: number): [number, string] {
  if (rom < THRESHOLDS.kneeRomLowSevere)
    return [2, `Severely restricted knee ROM (${rom.toFixed(1)}°). Values below 50° indicate significant joint stiffness.`];
  if (rom < THRESHOLDS.kneeRomLowWarn)
    return [1, `Mildly restricted knee ROM (${rom.toFixed(1)}°). Normal walking requires 55–75°.`];
  if (rom > 80)
    return [1, `Elevated knee ROM (${rom.toFixed(1)}°). Hyperflexion may indicate joint instability.`];
  return [0, `Knee ROM within normal range (${rom.toFixed(1)}°).`];
}

function scoreKneeAsymmetry(asym: number): [number, string] {
  if (asym > THRESHOLDS.kneeAsymSevere)
    return [2, `Significant L/R knee asymmetry (${asym.toFixed(1)}°). Suggests compensatory offloading.`];
  if (asym > THRESHOLDS.kneeAsymWarn)
    return [1, `Mild knee asymmetry (${asym.toFixed(1)}°). Monitor for progressive imbalance.`];
  return [0, `Knee symmetry within normal range (${asym.toFixed(1)}°).`];
}

function scoreHipSway(sway: number): [number, string] {
  if (sway > THRESHOLDS.hipSwaySevere)
    return [2, `Excessive hip sway (${sway.toFixed(1)}%). May indicate abductor weakness.`];
  if (sway > THRESHOLDS.hipSwayWarn)
    return [1, `Elevated hip sway (${sway.toFixed(1)}%). Minor lateral imbalance.`];
  return [0, `Hip sway within normal range (${sway.toFixed(1)}%).`];
}

function scoreStrideCv(cv: number): [number, string] {
  if (cv > THRESHOLDS.strideCvSevere)
    return [2, `Highly irregular stride timing (CV=${cv.toFixed(1)}%). Pain-avoidance gait pattern.`];
  if (cv > THRESHOLDS.strideCvWarn)
    return [1, `Moderately irregular stride timing (CV=${cv.toFixed(1)}%).`];
  return [0, `Stride timing regular (CV=${cv.toFixed(1)}%).`];
}

function scoreStance(ratio: number, side: string): [number, string] {
  const pct = (ratio * 100).toFixed(1);
  if (ratio < THRESHOLDS.stanceLowWarn || ratio > THRESHOLDS.stanceHighWarn)
    return [1, `${side} stance phase abnormal (${pct}%). Normal: 60–65%. Antalgic gait indicator.`];
  return [0, `${side} stance ratio normal (${pct}%).`];
}

function scorePressureAsymmetry(asym: number): [number, string] {
  if (asym > THRESHOLDS.pressureAsymSevere)
    return [2, `Severe pressure asymmetry (${asym.toFixed(1)}%). Significant unilateral offloading.`];
  if (asym > THRESHOLDS.pressureAsymWarn)
    return [1, `Moderate pressure asymmetry (${asym.toFixed(1)}%). Monitor weight distribution.`];
  return [0, `Foot pressure distribution balanced (${asym.toFixed(1)}%).`];
}

// ── Public classifier ─────────────────────────────────────────────────────────

export function classifyRisk(metrics: GaitMetrics): RiskAssessment {
  const MIN_VALID_CADENCE = 30; // spm — below this means insufficient data
  if (metrics.cadenceSPM < MIN_VALID_CADENCE) {
    return {
      score: 0,
      level: 'Low Risk',
      flaggedMarkers: [],
      summary: 'Insufficient gait data. Walk for at least 5 seconds to generate a valid assessment.',
      dataValid: false,
    };
  }

  const markers: FlaggedMarker[] = [];
  let total = 0;

  const checks: [string, number, string, string, () => [number, string]][] = [
    ['Left Knee ROM',  metrics.leftKneeROM,    '°',  '55–75°',  () => scoreKneeRom(metrics.leftKneeROM)],
    ['Right Knee ROM', metrics.rightKneeROM,   '°',  '55–75°',  () => scoreKneeRom(metrics.rightKneeROM)],
    ['Knee Asymmetry', metrics.kneeAsymmetry,  '°',  '< 8°',    () => scoreKneeAsymmetry(metrics.kneeAsymmetry)],
    ['Hip Sway',       metrics.hipSwayAsymmetry,'%', '< 15%',   () => scoreHipSway(metrics.hipSwayAsymmetry)],
    ['Stride CV',      metrics.strideDurationCV,'%', '< 3%',    () => scoreStrideCv(metrics.strideDurationCV)],
    ['L Stance Ratio', metrics.leftStanceRatio, '',  '60–65%',  () => scoreStance(metrics.leftStanceRatio, 'Left')],
    ['R Stance Ratio', metrics.rightStanceRatio,'',  '60–65%',  () => scoreStance(metrics.rightStanceRatio, 'Right')],
    ['Pressure Asym.', metrics.pressureAsymmetry,'%','< 15%',   () => scorePressureAsymmetry(metrics.pressureAsymmetry)],
  ];

  for (const [name, value, unit, normalRange, scoreFn] of checks) {
    const [pts] = scoreFn();
    total += pts;
    if (pts > 0) {
      markers.push({ name, value, unit, normalRange, points: pts });
    }
  }

  const level: RiskLevel =
    total >= 6 ? 'High Risk / Potential OA' :
    total >= 3 ? 'Moderate — Monitor' :
    'Low Risk';

  const flaggedNames = markers.map(m => m.name).join(', ') || 'none';
  let summary = `Risk Score: ${total}. `;

  if (level === 'Low Risk') {
    summary += 'No significant OA markers detected. Gait parameters within published normal ranges.';
  } else if (level === 'Moderate — Monitor') {
    summary += `Flagged: ${flaggedNames}. Recommend follow-up clinical assessment.`;
  } else {
    summary += `Multiple OA markers: ${flaggedNames}. STRONGLY recommend specialist evaluation.`;
  }

  return { score: total, level, flaggedMarkers: markers, summary, dataValid: true };
}

// ── Metric aggregator (reduces N SensorFrames → GaitMetrics) ─────────────────

import type { SensorFrame } from '../types';

export function aggregateFrames(frames: SensorFrame[]): GaitMetrics {
  if (frames.length === 0) {
    return zeroMetrics();
  }

  const lk = frames.map(f => f.leftKneeAngle);
  const rk = frames.map(f => f.rightKneeAngle);
  const lp = frames.map(f => f.leftFootPressure);
  const rp = frames.map(f => f.rightFootPressure);
  const sw = frames.map(f => Math.abs(f.hipSwayX) * 100);

  const mean = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const std  = (arr: number[]) => {
    const m = mean(arr);
    return Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / arr.length);
  };

  const lkMean = mean(lk), rkMean = mean(rk);
  const lpMean = mean(lp), rpMean = mean(rp);

  const pressureTotal = lpMean + rpMean;
  const pressureAsym = pressureTotal > 0
    ? (Math.abs(lpMean - rpMean) / pressureTotal) * 100
    : 0;

  // Stride detection: count stance→swing transitions
  const stanceFrames = frames.filter(f => f.stridePhase === 'stance');
  const stanceRatioL = stanceFrames.filter(f => f.leftFootPressure > 50).length / frames.length;
  const stanceRatioR = stanceFrames.filter(f => f.rightFootPressure > 50).length / frames.length;

  const strideCv = lkMean > 0 ? (std(lk) / lkMean) * 100 : 0;

  // Cadence: estimate from stance phase transitions (~2 transitions per stride)
  const durationS = frames.length > 1
    ? (frames[frames.length - 1].timestamp - frames[0].timestamp) / 1000
    : 1;
  const cadence = durationS > 0 ? (stanceFrames.length / durationS) * 60 : 0;

  return {
    leftKneeAngle:    lkMean,
    rightKneeAngle:   rkMean,
    kneeAsymmetry:    Math.abs(lkMean - rkMean),
    leftKneeROM:      Math.max(...lk) - Math.min(...lk),
    rightKneeROM:     Math.max(...rk) - Math.min(...rk),
    leftFootPressure:  lpMean,
    rightFootPressure: rpMean,
    pressureAsymmetry: pressureAsym,
    strideAsymmetry:   Math.abs(stanceRatioL - stanceRatioR) * 100,
    strideDurationCV:  Math.min(strideCv, 30),
    cadenceSPM:        Math.min(cadence, 200),
    leftStanceRatio:   Math.min(stanceRatioL, 1),
    rightStanceRatio:  Math.min(stanceRatioR, 1),
    hipSwayAsymmetry:  mean(sw),
  };
}

function zeroMetrics(): GaitMetrics {
  return {
    leftKneeAngle: 0, rightKneeAngle: 0, kneeAsymmetry: 0,
    leftKneeROM: 0, rightKneeROM: 0,
    leftFootPressure: 0, rightFootPressure: 0, pressureAsymmetry: 0,
    strideAsymmetry: 0, strideDurationCV: 0, cadenceSPM: 0,
    leftStanceRatio: 0.62, rightStanceRatio: 0.62,
    hipSwayAsymmetry: 0,
  };
}
