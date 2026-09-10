// src/components/RiskBadge.tsx
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import type { RiskLevel } from '../types';

interface Props {
  level:    RiskLevel;
  score?:   number;
  compact?: boolean;
}

function riskConfig(level: RiskLevel) {
  switch (level) {
    case 'Low Risk':
      return {
        colors:   ['#003820', '#005C30'] as [string, string],
        accent:   Colors.riskLow,
        icon:     'checkmark-circle' as const,
        label:    'LOW RISK',
        emoji:    '🟢',
      };
    case 'Moderate — Monitor':
      return {
        colors:   ['#3D2800', '#5C3D00'] as [string, string],
        accent:   Colors.riskMod,
        icon:     'warning' as const,
        label:    'MODERATE',
        emoji:    '🟡',
      };
    case 'High Risk / Potential OA':
      return {
        colors:   ['#3D0000', '#5C0000'] as [string, string],
        accent:   Colors.riskHigh,
        icon:     'alert-circle' as const,
        label:    'HIGH RISK',
        emoji:    '🔴',
      };
  }
}

export function RiskBadge({ level, score, compact = false }: Props) {
  const cfg   = riskConfig(level);
  const scale = useRef(new Animated.Value(0.85)).current;

  useEffect(() => {
    Animated.spring(scale, {
      toValue: 1,
      tension: 80,
      friction: 6,
      useNativeDriver: true,
    }).start();
  }, [level]);

  if (compact) {
    return (
      <View style={[styles.compactBadge, { borderColor: cfg.accent }]}>
        <Ionicons name={cfg.icon} size={12} color={cfg.accent} />
        <Text style={[styles.compactLabel, { color: cfg.accent }]}>{cfg.label}</Text>
      </View>
    );
  }

  return (
    <Animated.View style={[styles.wrapper, Shadows.glow, { transform: [{ scale }] }]}>
      <LinearGradient colors={cfg.colors} style={styles.gradient}>
        <View style={[styles.iconCircle, { backgroundColor: cfg.accent + '22', borderColor: cfg.accent + '55' }]}>
          <Ionicons name={cfg.icon} size={32} color={cfg.accent} />
        </View>
        <Text style={[styles.levelLabel, { color: cfg.accent }]}>{cfg.label}</Text>
        <Text style={styles.levelFull}>{level}</Text>
        {score !== undefined && (
          <View style={[styles.scorePill, { backgroundColor: cfg.accent + '22', borderColor: cfg.accent + '55' }]}>
            <Text style={[styles.scoreText, { color: cfg.accent }]}>Score: {score}</Text>
          </View>
        )}
      </LinearGradient>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    borderRadius: Radius.lg,
    overflow: 'hidden',
  },
  gradient: {
    alignItems: 'center',
    padding: Spacing.xl,
    gap: Spacing.sm,
  },
  iconCircle: {
    width: 72, height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    marginBottom: Spacing.sm,
  },
  levelLabel: {
    fontSize: Typography.fontSizeXL,
    fontWeight: Typography.fontWeightHeavy,
    letterSpacing: Typography.letterSpacingXWide,
  },
  levelFull: {
    fontSize: Typography.fontSizeMD,
    color: Colors.textSecondary,
    textAlign: 'center',
    fontWeight: Typography.fontWeightMedium,
  },
  scorePill: {
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radius.full,
    borderWidth: 1,
  },
  scoreText: {
    fontSize: Typography.fontSizeSM,
    fontWeight: Typography.fontWeightSemiBold,
    letterSpacing: Typography.letterSpacingWide,
  },
  // Compact
  compactBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: Radius.full,
    borderWidth: 1,
    backgroundColor: Colors.bgCard,
  },
  compactLabel: {
    fontSize: Typography.fontSizeXS,
    fontWeight: Typography.fontWeightBold,
    letterSpacing: Typography.letterSpacingWide,
  },
});
