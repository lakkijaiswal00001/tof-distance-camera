// src/components/MetricCard.tsx
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';

interface Props {
  label:       string;
  value:       number | string;
  unit?:       string;
  normalRange?: string;
  accentColor?: string;
  flagged?:    boolean;
  icon?:       React.ReactNode;
  subtitle?:   string;
}

export function MetricCard({
  label, value, unit = '', normalRange,
  accentColor = Colors.accent, flagged = false,
  icon, subtitle,
}: Props) {
  const anim  = useRef(new Animated.Value(0)).current;
  const prevValue = useRef(typeof value === 'number' ? value : 0);

  useEffect(() => {
    if (typeof value !== 'number') return;
    const diff = Math.abs(value - prevValue.current);
    if (diff > 0.5) {
      Animated.sequence([
        Animated.timing(anim, { toValue: 1, duration: 120, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0, duration: 300, useNativeDriver: true }),
      ]).start();
      prevValue.current = value;
    }
  }, [value]);

  const flashBg = anim.interpolate({
    inputRange:  [0, 1],
    outputRange: [Colors.bgCard, accentColor + '22'],
  });

  const borderColor = flagged ? Colors.riskHigh : (accentColor + '44');

  return (
    <Animated.View style={[
      styles.card,
      Shadows.card,
      { borderColor, backgroundColor: flashBg },
    ]}>
      {/* Header row */}
      <View style={styles.headerRow}>
        {icon && <View style={styles.iconWrap}>{icon}</View>}
        <Text style={styles.label}>{label}</Text>
        {flagged && (
          <View style={styles.flagPill}>
            <Text style={styles.flagText}>!</Text>
          </View>
        )}
      </View>

      {/* Value */}
      <View style={styles.valueRow}>
        <Text style={[styles.value, { color: flagged ? Colors.riskHigh : accentColor }]}>
          {typeof value === 'number' ? value.toFixed(1) : value}
        </Text>
        {unit ? <Text style={[styles.unit, { color: accentColor + 'BB' }]}>{unit}</Text> : null}
      </View>

      {/* Normal range */}
      {normalRange && (
        <Text style={styles.normalRange}>Normal: {normalRange}</Text>
      )}
      {subtitle && (
        <Text style={styles.subtitle}>{subtitle}</Text>
      )}

      {/* Bottom accent bar */}
      <View style={[styles.accentBar, { backgroundColor: flagged ? Colors.riskHigh : accentColor }]} />
    </Animated.View>
  );
}

// ── Dual-value variant (Left / Right) ─────────────────────────────────────────
interface DualProps {
  label:        string;
  leftValue:    number;
  rightValue:   number;
  unit?:        string;
  normalRange?: string;
  accentColor?: string;
  flagged?:     boolean;
}

export function DualMetricCard({ label, leftValue, rightValue, unit = '', normalRange, accentColor = Colors.accent, flagged = false }: DualProps) {
  return (
    <View style={[styles.card, Shadows.card, { borderColor: flagged ? Colors.riskHigh : accentColor + '44' }]}>
      <Text style={styles.label}>{label}</Text>
      <View style={styles.dualRow}>
        <View style={styles.dualSide}>
          <Text style={styles.dualSideLabel}>LEFT</Text>
          <Text style={[styles.dualValue, { color: accentColor }]}>{leftValue.toFixed(1)}<Text style={styles.unit}>{unit}</Text></Text>
        </View>
        <View style={[styles.dualDivider, { backgroundColor: accentColor + '33' }]} />
        <View style={styles.dualSide}>
          <Text style={styles.dualSideLabel}>RIGHT</Text>
          <Text style={[styles.dualValue, { color: accentColor }]}>{rightValue.toFixed(1)}<Text style={styles.unit}>{unit}</Text></Text>
        </View>
      </View>
      {normalRange && <Text style={styles.normalRange}>Normal: {normalRange}</Text>}
      <View style={[styles.accentBar, { backgroundColor: flagged ? Colors.riskHigh : accentColor }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.bgCard,
    borderRadius:    Radius.md,
    padding:         Spacing.md,
    borderWidth:     1,
    overflow:        'hidden',
    flex: 1,
    minWidth: 150,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xs,
    gap: Spacing.xs,
  },
  iconWrap: { marginRight: 2 },
  label: {
    fontSize:    Typography.fontSizeXS,
    color:       Colors.textSecondary,
    fontWeight:  Typography.fontWeightSemiBold,
    letterSpacing: Typography.letterSpacingXWide,
    flex: 1,
  },
  flagPill: {
    width: 16, height: 16,
    borderRadius: 8,
    backgroundColor: Colors.riskHigh,
    alignItems: 'center',
    justifyContent: 'center',
  },
  flagText: { fontSize: 9, color: '#fff', fontWeight: '800' },
  valueRow: {
    flexDirection: 'row',
    alignItems:   'baseline',
    gap: 3,
  },
  value: {
    fontSize:   Typography.fontSizeXXL,
    fontWeight: Typography.fontWeightHeavy,
    letterSpacing: Typography.letterSpacingTight,
  },
  unit: {
    fontSize:  Typography.fontSizeMD,
    color:     Colors.textSecondary,
    fontWeight: Typography.fontWeightMedium,
  },
  normalRange: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textMuted,
    marginTop: Spacing.xs,
  },
  subtitle: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textMuted,
    marginTop: 2,
  },
  accentBar: {
    position: 'absolute',
    bottom: 0, left: 0, right: 0,
    height: 3,
    borderRadius: 2,
  },
  // Dual
  dualRow: {
    flexDirection: 'row',
    alignItems:   'center',
    marginTop: Spacing.xs,
    gap: Spacing.sm,
  },
  dualSide:   { flex: 1, alignItems: 'center' },
  dualSideLabel: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textMuted,
    letterSpacing: Typography.letterSpacingWide,
    marginBottom: 2,
  },
  dualValue: {
    fontSize:   Typography.fontSizeXL,
    fontWeight: Typography.fontWeightHeavy,
  },
  dualDivider: {
    width: 1,
    height: 36,
  },
});
