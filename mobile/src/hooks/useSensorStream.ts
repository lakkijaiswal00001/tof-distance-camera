// src/hooks/useSensorStream.ts
// ─────────────────────────────────────────────────────────────────────────────
// Hook that manages the sensor stream lifecycle and aggregates
// incoming SensorFrames into live GaitMetrics + RiskAssessment.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useRef, useCallback } from 'react';
import { startSensorStream, stopSensorStream, setSensorProfile, type GaitProfile } from '../services/sensorService';
import { aggregateFrames, classifyRisk } from '../services/gaitAnalyzer';
import type { SensorFrame, GaitMetrics, RiskAssessment } from '../types';

const BUFFER_SIZE = 150;  // ~5 s at 30 fps
const CLASSIFY_EVERY = 30; // re-classify every 30 frames (1 s)

interface UseSensorStreamReturn {
  isStreaming:   boolean;
  latestFrame:   SensorFrame | null;
  metrics:       GaitMetrics | null;
  assessment:    RiskAssessment | null;
  frameCount:    number;
  startStream:   (profile?: GaitProfile) => void;
  stopStream:    () => void;
  setProfile:    (profile: GaitProfile) => void;
  resetBuffer:   () => void;
}

export function useSensorStream(): UseSensorStreamReturn {
  const [isStreaming,   setIsStreaming]   = useState(false);
  const [latestFrame,   setLatestFrame]   = useState<SensorFrame | null>(null);
  const [metrics,       setMetrics]       = useState<GaitMetrics | null>(null);
  const [assessment,    setAssessment]    = useState<RiskAssessment | null>(null);
  const [frameCount,    setFrameCount]    = useState(0);

  const buffer    = useRef<SensorFrame[]>([]);
  const frameIdx  = useRef(0);

  const handleFrame = useCallback((frame: SensorFrame) => {
    // Rolling buffer
    buffer.current.push(frame);
    if (buffer.current.length > BUFFER_SIZE) {
      buffer.current.shift();
    }

    frameIdx.current += 1;
    setLatestFrame(frame);
    setFrameCount(c => c + 1);

    // Re-classify periodically (not every frame — avoid thrashing)
    if (frameIdx.current % CLASSIFY_EVERY === 0) {
      const agg = aggregateFrames(buffer.current);
      const risk = classifyRisk(agg);
      setMetrics(agg);
      setAssessment(risk);
    }
  }, []);

  const startStream = useCallback((profile: GaitProfile = 'normal') => {
    startSensorStream(handleFrame, profile);
    setIsStreaming(true);
  }, [handleFrame]);

  const stopStream = useCallback(() => {
    stopSensorStream();
    setIsStreaming(false);
    // Final metrics on stop
    if (buffer.current.length > 0) {
      const agg  = aggregateFrames(buffer.current);
      const risk = classifyRisk(agg);
      setMetrics(agg);
      setAssessment(risk);
    }
  }, []);

  const setProfile = useCallback((profile: GaitProfile) => {
    setSensorProfile(profile);
  }, []);

  const resetBuffer = useCallback(() => {
    buffer.current = [];
    frameIdx.current = 0;
    setFrameCount(0);
    setMetrics(null);
    setAssessment(null);
    setLatestFrame(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => { stopSensorStream(); };
  }, []);

  return {
    isStreaming,
    latestFrame,
    metrics,
    assessment,
    frameCount,
    startStream,
    stopStream,
    setProfile,
    resetBuffer,
  };
}
