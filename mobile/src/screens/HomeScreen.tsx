// src/screens/HomeScreen.tsx
import React, { useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView,
  StyleSheet, Animated, Dimensions,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { OfflineIndicator } from '../components/OfflineIndicator';
import { RiskBadge } from '../components/RiskBadge';
import { useDatabase } from '../hooks/useDatabase';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { RootTabParamList } from '../types';

const { width: W } = Dimensions.get('window');

interface Props {
  navigation: BottomTabNavigationProp<RootTabParamList>;
}

const QUICK_ACTIONS = [
  { icon: 'videocam',        label: 'Camera\nScreening', tab: 'Camera'    as const, color: Colors.accent,          grad: ['#003D35', '#00E5C8'] as [string,string] },
  { icon: 'pulse',           label: 'Live\nDashboard',  tab: 'Dashboard' as const, color: Colors.metricPressure,   grad: ['#1E0A3D', '#7C4DFF'] as [string,string] },
  { icon: 'time',            label: 'Session\nHistory', tab: 'History'   as const, color: Colors.metricStride,     grad: ['#3D1500', '#FF6B35'] as [string,string] },
];

export function HomeScreen({ navigation }: Props) {
  const { sessions, loadSessions } = useDatabase();

  const heroAnim  = useRef(new Animated.Value(0)).current;
  const cardAnim  = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadSessions();
    Animated.stagger(120, [
      Animated.timing(heroAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
      Animated.timing(cardAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
    ]).start();
  }, []);

  const latest = sessions[0];

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Hero header */}
        <LinearGradient colors={['#0D1F3A', Colors.bg]} style={styles.hero}>
          <Animated.View style={{ opacity: heroAnim, transform: [{ translateY: heroAnim.interpolate({ inputRange: [0,1], outputRange: [20, 0] }) }] }}>
            <View style={styles.heroTop}>
              <View>
                <Text style={styles.appName}>OA Gait Screener</Text>
                <Text style={styles.appSub}>Early Osteoarthritis Detection</Text>
              </View>
              <OfflineIndicator />
            </View>

            {/* Hero illustration strip */}
            <View style={styles.heroStrip}>
              <LinearGradient
                colors={[Colors.accentGlow, 'transparent']}
                style={styles.heroGlow}
              />
              <View style={styles.heroIconRow}>
                {['walk-outline', 'body-outline', 'analytics-outline'].map((icon, i) => (
                  <View key={i} style={[styles.heroIcon, { backgroundColor: Colors.accentGlow }]}>
                    <Ionicons name={icon as any} size={28} color={Colors.accent} />
                  </View>
                ))}
              </View>
              <Text style={styles.heroTagline}>
                Walk. Analyse. Detect Early. Act.
              </Text>
              <Text style={styles.heroDesc}>
                100% offline • Runs locally on device • No cloud dependency
              </Text>
            </View>
          </Animated.View>
        </LinearGradient>

        {/* Quick actions */}
        <Animated.View style={[styles.section, { opacity: cardAnim }]}>
          <Text style={styles.sectionTitle}>QUICK ACTIONS</Text>
          <View style={styles.actionsRow}>
            {QUICK_ACTIONS.map((action, i) => (
              <TouchableOpacity
                key={i}
                style={[styles.actionCard, Shadows.card]}
                onPress={() => navigation.navigate(action.tab)}
                activeOpacity={0.75}
              >
                <LinearGradient colors={action.grad} style={styles.actionGrad}>
                  <View style={[styles.actionIconCircle, { backgroundColor: '#ffffff22' }]}>
                    <Ionicons name={action.icon as any} size={26} color="#fff" />
                  </View>
                  <Text style={styles.actionLabel}>{action.label}</Text>
                </LinearGradient>
              </TouchableOpacity>
            ))}
          </View>
        </Animated.View>

        {/* Last session summary */}
        {latest && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>LAST SESSION</Text>
            <TouchableOpacity
              style={[styles.lastSessionCard, Shadows.card]}
              onPress={() => navigation.navigate('History')}
              activeOpacity={0.8}
            >
              <LinearGradient
                colors={[Colors.bgElevated, Colors.bgCard]}
                style={styles.lastSessionGrad}
              >
                <View style={styles.lastSessionTop}>
                  <RiskBadge level={latest.riskLevel} score={latest.riskScore} compact />
                  <Text style={styles.lastSessionDate}>
                    {new Date(latest.timestamp).toLocaleDateString('en-IN', {
                      day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit', hour12: true
                    })}
                  </Text>
                </View>
                <View style={styles.lastMetricRow}>
                  <LastMetric label="L Knee" value={`${latest.metrics.leftKneeAngle.toFixed(0)}°`}  color={Colors.metricKnee} />
                  <LastMetric label="R Knee" value={`${latest.metrics.rightKneeAngle.toFixed(0)}°`} color={Colors.metricKnee} />
                  <LastMetric label="Asym"   value={`${latest.metrics.kneeAsymmetry.toFixed(1)}°`} color={Colors.riskMod} />
                  <LastMetric label="Cadence" value={`${latest.metrics.cadenceSPM.toFixed(0)}`}    color={Colors.metricStride} />
                </View>
                <Text style={styles.lastSummary} numberOfLines={2}>{latest.summary}</Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        )}

        {/* Info tiles */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>HOW IT WORKS</Text>
          {STEPS.map((step, i) => (
            <View key={i} style={[styles.stepCard, Shadows.card]}>
              <View style={[styles.stepNum, { backgroundColor: Colors.accent + '22', borderColor: Colors.accent + '55' }]}>
                <Text style={[styles.stepNumText, { color: Colors.accent }]}>{i + 1}</Text>
              </View>
              <View style={styles.stepBody}>
                <Text style={styles.stepTitle}>{step.title}</Text>
                <Text style={styles.stepDesc}>{step.desc}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* Disclaimer */}
        <View style={styles.disclaimer}>
          <Ionicons name="information-circle-outline" size={16} color={Colors.textMuted} />
          <Text style={styles.disclaimerText}>
            This tool is for screening purposes only and does not constitute a clinical diagnosis.
            Always consult a qualified healthcare professional.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function LastMetric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={styles.lastMetric}>
      <Text style={[styles.lastMetricVal, { color }]}>{value}</Text>
      <Text style={styles.lastMetricLabel}>{label}</Text>
    </View>
  );
}

const STEPS = [
  { title: 'Position & Align',  desc: 'Open Camera Screening and stand 2–3m from the device. Follow the alignment guide to ensure your full body is visible.' },
  { title: 'Record Your Gait',  desc: 'Walk naturally for 10–15 seconds. The system extracts knee angles, stride timing, and hip sway in real time.' },
  { title: 'Review Results',    desc: 'View your risk stratification, flagged markers, and recommendations. Save the session for tracking over time.' },
];

const styles = StyleSheet.create({
  root:    { flex: 1, backgroundColor: Colors.bg },
  content: { paddingBottom: 80 },

  hero:    { padding: Spacing.lg, paddingTop: Spacing.xl },
  heroTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: Spacing.lg },
  appName: { fontSize: Typography.fontSizeXXL, color: Colors.textPrimary, fontWeight: Typography.fontWeightHeavy, letterSpacing: Typography.letterSpacingTight },
  appSub:  { fontSize: Typography.fontSizeSM,  color: Colors.accent, fontWeight: Typography.fontWeightMedium, letterSpacing: Typography.letterSpacingWide },

  heroStrip:   { backgroundColor: Colors.bgCard, borderRadius: Radius.lg, padding: Spacing.lg, borderWidth: 1, borderColor: Colors.border },
  heroGlow:    { position: 'absolute', top: 0, left: 0, right: 0, height: 80, borderTopLeftRadius: Radius.lg, borderTopRightRadius: Radius.lg },
  heroIconRow: { flexDirection: 'row', gap: Spacing.lg, marginBottom: Spacing.md },
  heroIcon:    { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  heroTagline: { fontSize: Typography.fontSizeLG, color: Colors.textPrimary, fontWeight: Typography.fontWeightBold, marginBottom: Spacing.xs },
  heroDesc:    { fontSize: Typography.fontSizeSM, color: Colors.textSecondary },

  section:      { paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg, gap: Spacing.sm },
  sectionTitle: { fontSize: Typography.fontSizeXS, color: Colors.textMuted, letterSpacing: Typography.letterSpacingXWide, fontWeight: Typography.fontWeightSemiBold },

  actionsRow: { flexDirection: 'row', gap: Spacing.sm },
  actionCard: { flex: 1, borderRadius: Radius.md, overflow: 'hidden' },
  actionGrad: { padding: Spacing.md, alignItems: 'center', gap: Spacing.sm, minHeight: 110 },
  actionIconCircle: { width: 52, height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  actionLabel: { fontSize: Typography.fontSizeXS, color: '#fff', fontWeight: Typography.fontWeightBold, letterSpacing: Typography.letterSpacingWide, textAlign: 'center' },

  lastSessionCard: { borderRadius: Radius.md, overflow: 'hidden' },
  lastSessionGrad: { padding: Spacing.md, gap: Spacing.sm },
  lastSessionTop:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  lastSessionDate: { fontSize: Typography.fontSizeXS, color: Colors.textSecondary },
  lastMetricRow:   { flexDirection: 'row', gap: Spacing.md },
  lastMetric:      { alignItems: 'center' },
  lastMetricVal:   { fontSize: Typography.fontSizeLG, fontWeight: Typography.fontWeightBold },
  lastMetricLabel: { fontSize: Typography.fontSizeXS, color: Colors.textMuted },
  lastSummary:     { fontSize: Typography.fontSizeXS, color: Colors.textSecondary, lineHeight: 18 },

  stepCard: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.md,
    backgroundColor: Colors.bgCard, borderRadius: Radius.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  stepNum:     { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  stepNumText: { fontSize: Typography.fontSizeSM, fontWeight: Typography.fontWeightBold },
  stepBody:    { flex: 1, gap: 4 },
  stepTitle:   { fontSize: Typography.fontSizeMD, color: Colors.textPrimary, fontWeight: Typography.fontWeightSemiBold },
  stepDesc:    { fontSize: Typography.fontSizeSM, color: Colors.textSecondary, lineHeight: 20 },

  disclaimer: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.xs,
    margin: Spacing.lg,
    padding: Spacing.md,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  disclaimerText: { fontSize: Typography.fontSizeXS, color: Colors.textMuted, lineHeight: 18, flex: 1 },
});
