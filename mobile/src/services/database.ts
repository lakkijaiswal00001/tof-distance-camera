// src/services/database.ts
// ─────────────────────────────────────────────────────────────────────────────
// expo-sqlite local database — offline-first session storage
// Schema: screening_sessions (metadata) + gait_metrics (linked metrics)
// ─────────────────────────────────────────────────────────────────────────────

import * as SQLite from 'expo-sqlite';
import type { ScreeningSession, GaitMetrics, RiskAssessment } from '../types';

const DB_NAME = 'oa_gait.db';
let db: SQLite.SQLiteDatabase | null = null;

// ── Open / init ───────────────────────────────────────────────────────────────

export async function openDatabase(): Promise<void> {
  try {
    db = await SQLite.openDatabaseAsync(DB_NAME);
    await db.execAsync(`PRAGMA journal_mode = WAL;`);
    await db.execAsync(`PRAGMA foreign_keys = ON;`);
    await createTables();
    console.log('[DB] Database ready:', DB_NAME);
  } catch (err) {
    console.error('[DB] Failed to open database:', err);
    throw err;
  }
}

async function createTables(): Promise<void> {
  if (!db) throw new Error('DB not initialised');
  await db.execAsync(`
    CREATE TABLE IF NOT EXISTS screening_sessions (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp        TEXT    NOT NULL,
      duration_seconds REAL    NOT NULL DEFAULT 0,
      mode             TEXT    NOT NULL DEFAULT 'sensor',
      risk_level       TEXT    NOT NULL,
      risk_score       INTEGER NOT NULL DEFAULT 0,
      data_valid       INTEGER NOT NULL DEFAULT 1,
      summary          TEXT    NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS gait_metrics (
      id                      INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id              INTEGER NOT NULL
                                REFERENCES screening_sessions(id) ON DELETE CASCADE,
      left_knee_angle         REAL,
      right_knee_angle        REAL,
      knee_asymmetry          REAL,
      left_knee_rom           REAL,
      right_knee_rom          REAL,
      left_foot_pressure      REAL,
      right_foot_pressure     REAL,
      pressure_asymmetry      REAL,
      stride_asymmetry        REAL,
      stride_duration_cv      REAL,
      cadence_spm             REAL,
      left_stance_ratio       REAL,
      right_stance_ratio      REAL,
      hip_sway_asymmetry      REAL
    );
  `);
}

// ── Write ─────────────────────────────────────────────────────────────────────

export async function saveSession(
  assessment: RiskAssessment,
  metrics: GaitMetrics,
  mode: ScreeningSession['mode'] = 'sensor',
  durationSeconds: number = 0,
): Promise<number> {
  if (!db) throw new Error('DB not initialised');

  const timestamp = new Date().toISOString();

  const result = await db.runAsync(
    `INSERT INTO screening_sessions
       (timestamp, duration_seconds, mode, risk_level, risk_score, data_valid, summary)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [
      timestamp,
      durationSeconds,
      mode,
      assessment.level,
      assessment.score,
      assessment.dataValid ? 1 : 0,
      assessment.summary,
    ],
  );

  const sessionId = result.lastInsertRowId;

  await db.runAsync(
    `INSERT INTO gait_metrics
       (session_id,
        left_knee_angle, right_knee_angle, knee_asymmetry,
        left_knee_rom, right_knee_rom,
        left_foot_pressure, right_foot_pressure, pressure_asymmetry,
        stride_asymmetry, stride_duration_cv, cadence_spm,
        left_stance_ratio, right_stance_ratio, hip_sway_asymmetry)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      sessionId,
      metrics.leftKneeAngle,  metrics.rightKneeAngle, metrics.kneeAsymmetry,
      metrics.leftKneeROM,    metrics.rightKneeROM,
      metrics.leftFootPressure, metrics.rightFootPressure, metrics.pressureAsymmetry,
      metrics.strideAsymmetry, metrics.strideDurationCV, metrics.cadenceSPM,
      metrics.leftStanceRatio, metrics.rightStanceRatio,  metrics.hipSwayAsymmetry,
    ],
  );

  console.log(`[DB] Session #${sessionId} saved.`);
  return sessionId;
}

// ── Read ──────────────────────────────────────────────────────────────────────

export async function getAllSessions(limit = 50): Promise<ScreeningSession[]> {
  if (!db) throw new Error('DB not initialised');

  const rows = await db.getAllAsync<any>(
    `SELECT
       s.id, s.timestamp, s.duration_seconds, s.mode,
       s.risk_level, s.risk_score, s.data_valid, s.summary,
       m.left_knee_angle, m.right_knee_angle, m.knee_asymmetry,
       m.left_knee_rom, m.right_knee_rom,
       m.left_foot_pressure, m.right_foot_pressure, m.pressure_asymmetry,
       m.stride_asymmetry, m.stride_duration_cv, m.cadence_spm,
       m.left_stance_ratio, m.right_stance_ratio, m.hip_sway_asymmetry
     FROM screening_sessions s
     LEFT JOIN gait_metrics m ON m.session_id = s.id
     ORDER BY s.id DESC
     LIMIT ?`,
    [limit],
  );

  return rows.map(rowToSession);
}

export async function getSessionById(id: number): Promise<ScreeningSession | null> {
  if (!db) throw new Error('DB not initialised');

  const row = await db.getFirstAsync<any>(
    `SELECT
       s.id, s.timestamp, s.duration_seconds, s.mode,
       s.risk_level, s.risk_score, s.data_valid, s.summary,
       m.left_knee_angle, m.right_knee_angle, m.knee_asymmetry,
       m.left_knee_rom, m.right_knee_rom,
       m.left_foot_pressure, m.right_foot_pressure, m.pressure_asymmetry,
       m.stride_asymmetry, m.stride_duration_cv, m.cadence_spm,
       m.left_stance_ratio, m.right_stance_ratio, m.hip_sway_asymmetry
     FROM screening_sessions s
     LEFT JOIN gait_metrics m ON m.session_id = s.id
     WHERE s.id = ?`,
    [id],
  );
  return row ? rowToSession(row) : null;
}

export async function getSessionCount(): Promise<number> {
  if (!db) throw new Error('DB not initialised');
  const row = await db.getFirstAsync<{ count: number }>(
    'SELECT COUNT(*) as count FROM screening_sessions'
  );
  return row?.count ?? 0;
}

export async function deleteSession(id: number): Promise<void> {
  if (!db) throw new Error('DB not initialised');
  await db.runAsync('DELETE FROM screening_sessions WHERE id = ?', [id]);
}

// ── Row mapper ────────────────────────────────────────────────────────────────

function rowToSession(r: any): ScreeningSession {
  return {
    id:              r.id,
    timestamp:       r.timestamp,
    durationSeconds: r.duration_seconds,
    mode:            r.mode,
    riskLevel:       r.risk_level,
    riskScore:       r.risk_score,
    summary:         r.summary,
    dataValid:       Boolean(r.data_valid),
    metrics: {
      leftKneeAngle:     r.left_knee_angle   ?? 0,
      rightKneeAngle:    r.right_knee_angle  ?? 0,
      kneeAsymmetry:     r.knee_asymmetry    ?? 0,
      leftKneeROM:       r.left_knee_rom     ?? 0,
      rightKneeROM:      r.right_knee_rom    ?? 0,
      leftFootPressure:  r.left_foot_pressure  ?? 0,
      rightFootPressure: r.right_foot_pressure ?? 0,
      pressureAsymmetry: r.pressure_asymmetry  ?? 0,
      strideAsymmetry:   r.stride_asymmetry    ?? 0,
      strideDurationCV:  r.stride_duration_cv  ?? 0,
      cadenceSPM:        r.cadence_spm         ?? 0,
      leftStanceRatio:   r.left_stance_ratio   ?? 0.62,
      rightStanceRatio:  r.right_stance_ratio  ?? 0.62,
      hipSwayAsymmetry:  r.hip_sway_asymmetry  ?? 0,
    },
  };
}
