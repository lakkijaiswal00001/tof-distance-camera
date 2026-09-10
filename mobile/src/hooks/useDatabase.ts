// src/hooks/useDatabase.ts
// ─────────────────────────────────────────────────────────────────────────────
// Database React hook — wraps service calls with loading/error state
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useCallback } from 'react';
import {
  saveSession,
  getAllSessions,
  getSessionById,
  getSessionCount,
  deleteSession,
} from '../services/database';
import type { ScreeningSession, RiskAssessment, GaitMetrics } from '../types';

interface UseDatabase {
  sessions:    ScreeningSession[];
  loading:     boolean;
  error:       string | null;
  loadSessions: () => Promise<void>;
  save: (
    assessment: RiskAssessment,
    metrics:    GaitMetrics,
    mode:       ScreeningSession['mode'],
    duration:   number,
  ) => Promise<number | null>;
  remove:      (id: number) => Promise<void>;
  sessionCount: () => Promise<number>;
}

export function useDatabase(): UseDatabase {
  const [sessions, setSessions] = useState<ScreeningSession[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAllSessions(50);
      setSessions(data);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load sessions');
      console.error('[DB Hook] loadSessions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const save = useCallback(async (
    assessment: RiskAssessment,
    metrics:    GaitMetrics,
    mode:       ScreeningSession['mode'],
    duration:   number,
  ): Promise<number | null> => {
    try {
      const id = await saveSession(assessment, metrics, mode, duration);
      await loadSessions();  // refresh list
      return id;
    } catch (err: any) {
      console.error('[DB Hook] save:', err);
      setError(err?.message ?? 'Failed to save session');
      return null;
    }
  }, [loadSessions]);

  const remove = useCallback(async (id: number) => {
    try {
      await deleteSession(id);
      setSessions(prev => prev.filter(s => s.id !== id));
    } catch (err: any) {
      console.error('[DB Hook] remove:', err);
      setError(err?.message ?? 'Failed to delete session');
    }
  }, []);

  const sessionCount = useCallback(async () => {
    try { return await getSessionCount(); }
    catch { return 0; }
  }, []);

  return { sessions, loading, error, loadSessions, save, remove, sessionCount };
}
