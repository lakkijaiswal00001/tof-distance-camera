// src/components/AlignmentGuide.tsx
// Overlay drawn on top of the camera preview to guide body positioning
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Typography, Spacing, Radius } from '../theme';

const { width: W, height: H } = Dimensions.get('window');

type AlignStatus = 'scanning' | 'partial' | 'ready';

interface Props {
  status:   AlignStatus;
  message:  string;
  onReady?: () => void;
}

function statusColor(s: AlignStatus) {
  switch (s) {
    case 'ready':   return Colors.riskLow;
    case 'partial': return Colors.riskMod;
    case 'scanning':return Colors.accent;
  }
}

function statusIcon(s: AlignStatus) {
  switch (s) {
    case 'ready':    return 'checkmark-circle';
    case 'partial':  return 'alert-circle';
    case 'scanning': return 'scan-outline';
  }
}

export function AlignmentGuide({ status, message }: Props) {
  const pulse = useRef(new Animated.Value(1)).current;
  const color = statusColor(status);

  useEffect(() => {
    if (status !== 'ready') {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 0.6, duration: 800, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1.0, duration: 800, useNativeDriver: true }),
        ])
      );
      loop.start();
      return () => loop.stop();
    } else {
      Animated.timing(pulse, { toValue: 1, duration: 200, useNativeDriver: true }).start();
    }
  }, [status]);

  // Guide box: 60% width, 85% height, centred
  const gw = W * 0.62;
  const gh = H * 0.78;
  const cornerLen = 24;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {/* Dimmed sides */}
      <View style={[styles.dimLeft,  { width: (W - gw) / 2 }]} />
      <View style={[styles.dimRight, { width: (W - gw) / 2 }]} />
      <View style={[styles.dimTop,   { height: (H - gh) / 2, width: gw, left: (W - gw) / 2 }]} />
      <View style={[styles.dimBot,   { height: (H - gh) / 2, width: gw, left: (W - gw) / 2 }]} />

      {/* Corner markers */}
      <Animated.View style={[styles.guideBox, {
        width: gw, height: gh,
        left:  (W - gw) / 2,
        top:   (H - gh) / 2,
        opacity: pulse,
      }]}>
        {/* TL */}
        <View style={[styles.corner, styles.tl, { borderColor: color, width: cornerLen, height: cornerLen }]} />
        {/* TR */}
        <View style={[styles.corner, styles.tr, { borderColor: color, width: cornerLen, height: cornerLen }]} />
        {/* BL */}
        <View style={[styles.corner, styles.bl, { borderColor: color, width: cornerLen, height: cornerLen }]} />
        {/* BR */}
        <View style={[styles.corner, styles.br, { borderColor: color, width: cornerLen, height: cornerLen }]} />

        {/* Human silhouette hint lines */}
        <View style={styles.silhouette}>
          {/* Head circle */}
          <View style={[styles.headCircle, { borderColor: color + '55' }]} />
          {/* Body line */}
          <View style={[styles.bodyLine,   { backgroundColor: color + '33' }]} />
        </View>
      </Animated.View>

      {/* Status banner */}
      <View style={[styles.banner, { borderColor: color + '66', backgroundColor: Colors.overlay }]}>
        <Ionicons name={statusIcon(status) as any} size={16} color={color} />
        <Text style={[styles.bannerText, { color }]}>{message}</Text>
      </View>

      {/* Top label */}
      <View style={styles.topLabel}>
        <Text style={styles.topLabelText}>ALIGN FULL BODY WITHIN FRAME</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  dimLeft:  { position: 'absolute', top: 0, left:  0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.55)' },
  dimRight: { position: 'absolute', top: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.55)' },
  dimTop:   { position: 'absolute', top: 0,           backgroundColor: 'rgba(0,0,0,0.55)' },
  dimBot:   { position: 'absolute', bottom: 0,        backgroundColor: 'rgba(0,0,0,0.55)' },

  guideBox: { position: 'absolute' },

  corner:   { position: 'absolute', borderWidth: 3 },
  tl: { top: 0, left:  0, borderBottomWidth: 0, borderRightWidth:  0 },
  tr: { top: 0, right: 0, borderBottomWidth: 0, borderLeftWidth:   0 },
  bl: { bottom: 0, left:  0, borderTopWidth: 0,  borderRightWidth: 0 },
  br: { bottom: 0, right: 0, borderTopWidth: 0,  borderLeftWidth:  0 },

  silhouette: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingTop: 20,
  },
  headCircle: {
    width: 44, height: 44,
    borderRadius: 22,
    borderWidth: 1.5,
    marginBottom: 8,
  },
  bodyLine: {
    width: 2,
    height: '60%',
    borderRadius: 1,
  },

  banner: {
    position:  'absolute',
    bottom:    40,
    left:      Spacing.lg,
    right:     Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    borderRadius: Radius.md,
    borderWidth: 1,
  },
  bannerText: {
    fontSize:   Typography.fontSizeSM,
    fontWeight: Typography.fontWeightSemiBold,
    flex: 1,
  },

  topLabel: {
    position:  'absolute',
    top:       16,
    left: 0, right: 0,
    alignItems: 'center',
  },
  topLabelText: {
    fontSize:    Typography.fontSizeXS,
    color:       Colors.textSecondary,
    letterSpacing: Typography.letterSpacingXWide,
    fontWeight:  Typography.fontWeightSemiBold,
    backgroundColor: Colors.overlay,
    paddingHorizontal: Spacing.md,
    paddingVertical:   4,
    borderRadius: Radius.full,
  },
});
