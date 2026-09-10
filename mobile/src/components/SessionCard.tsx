// src/components/SessionCard.tsx
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import { RiskBadge } from './RiskBadge';
import type { ScreeningSession } from '../types';

interface Props {
  session:  ScreeningSession;
  onPress:  () => void;
  onDelete: () => void;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: true,
    });
  } catch { return iso; }
}

function durationLabel(secs: number): string {
  if (secs < 60) return `${Math.round(secs)}s`;
  return `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s`;
}

export function SessionCard({ session, onPress, onDelete }: Props) {
  const riskColor =
    session.riskLevel === 'Low Risk'                ? Colors.riskLow :
    session.riskLevel === 'Moderate — Monitor'      ? Colors.riskMod :
    Colors.riskHigh;

  return (
    <TouchableOpacity
      style={[styles.card, Shadows.card, { borderLeftColor: riskColor }]}
      onPress={onPress}
      activeOpacity={0.75}
    >
      {/* Top row */}
      <View style={styles.topRow}>
        <View style={styles.idBadge}>
          <Text style={styles.idText}>#{session.id}</Text>
        </View>
        <Text style={styles.timestamp}>{formatDate(session.timestamp)}</Text>
        <TouchableOpacity onPress={onDelete} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Ionicons name="trash-outline" size={16} color={Colors.textMuted} />
        </TouchableOpacity>
      </View>

      {/* Risk level */}
      <View style={styles.riskRow}>
        <RiskBadge level={session.riskLevel} compact />
        <View style={[styles.scorePill, { borderColor: riskColor + '55' }]}>
          <Text style={[styles.scoreText, { color: riskColor }]}>Score {session.riskScore}</Text>
        </View>
      </View>

      {/* Metric pills */}
      <View style={styles.metricRow}>
        <MetricPill icon="body-outline"  label="L Knee" value={`${session.metrics.leftKneeAngle.toFixed(0)}°`}  color={Colors.metricKnee} />
        <MetricPill icon="body-outline"  label="R Knee" value={`${session.metrics.rightKneeAngle.toFixed(0)}°`} color={Colors.metricKnee} />
        <MetricPill icon="footsteps-outline" label="Cadence" value={`${session.metrics.cadenceSPM.toFixed(0)} spm`} color={Colors.metricStride} />
        <MetricPill icon="timer-outline" label="Duration" value={durationLabel(session.durationSeconds)} color={Colors.metricCadence} />
      </View>

      {/* Summary snippet */}
      <Text style={styles.summary} numberOfLines={2}>{session.summary}</Text>

      <View style={styles.chevron}>
        <Ionicons name="chevron-forward" size={16} color={Colors.textMuted} />
      </View>
    </TouchableOpacity>
  );
}

function MetricPill({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  return (
    <View style={[styles.pill, { borderColor: color + '44' }]}>
      <Text style={[styles.pillValue, { color }]}>{value}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius:    Radius.md,
    padding:         Spacing.md,
    marginBottom:    Spacing.sm,
    borderLeftWidth: 4,
    ...Shadows.card,
  },
  topRow: {
    flexDirection:  'row',
    alignItems:     'center',
    marginBottom:   Spacing.sm,
    gap:            Spacing.sm,
  },
  idBadge: {
    backgroundColor: Colors.bgElevated,
    borderRadius:    Radius.sm,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  idText: {
    fontSize:   Typography.fontSizeXS,
    color:      Colors.accent,
    fontWeight: Typography.fontWeightBold,
  },
  timestamp: {
    flex:       1,
    fontSize:   Typography.fontSizeXS,
    color:      Colors.textSecondary,
  },
  riskRow: {
    flexDirection: 'row',
    alignItems:    'center',
    gap:           Spacing.sm,
    marginBottom:  Spacing.sm,
  },
  scorePill: {
    borderWidth: 1,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  scoreText: {
    fontSize:   Typography.fontSizeXS,
    fontWeight: Typography.fontWeightBold,
  },
  metricRow: {
    flexDirection: 'row',
    flexWrap:      'wrap',
    gap:           Spacing.xs,
    marginBottom:  Spacing.sm,
  },
  pill: {
    borderWidth:     1,
    borderRadius:    Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical:   4,
    alignItems: 'center',
  },
  pillValue: {
    fontSize:   Typography.fontSizeSM,
    fontWeight: Typography.fontWeightBold,
  },
  pillLabel: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textMuted,
  },
  summary: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textSecondary,
    lineHeight: 18,
  },
  chevron: {
    position: 'absolute',
    right:    Spacing.md,
    top:      '50%',
  },
});
