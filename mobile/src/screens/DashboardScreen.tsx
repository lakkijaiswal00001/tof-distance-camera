// src/screens/DashboardScreen.tsx
import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, Alert, Animated,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';

import { MetricCard, DualMetricCard } from '../components/MetricCard';
import { RiskBadge } from '../components/RiskBadge';
import { OfflineIndicator } from '../components/OfflineIndicator';
import { useSensorStream } from '../hooks/useSensorStream';
import { useDatabase } from '../hooks/useDatabase';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import type { GaitProfile } from '../services/sensorService';

const PROFILES: { key: GaitProfile; label: string; color: string }[] = [
  { key: 'normal',    label: 'Normal',    color: Colors.riskLow  },
  { key: 'mild_oa',   label: 'Mild OA',   color: Colors.riskMod  },
  { key: 'severe_oa', label: 'Severe OA', color: Colors.riskHigh },
];

export function DashboardScreen() {
  const {
    isStreaming, latestFrame, metrics, assessment,
    frameCount, startStream, stopStream, setProfile, resetBuffer,
  } = useSensorStream();

  const { save } = useDatabase();
  const [selectedProfile, setSelectedProfile] = useState<GaitProfile>('normal');
  const [sessionStart,    setSessionStart]    = useState<number>(0);
  const [saved,           setSaved]           = useState(false);
  const streamAge = useRef(new Animated.Value(1)).current;

  // Flash on new frame
  useEffect(() => {
    if (!latestFrame) return;
    Animated.sequence([
      Animated.timing(streamAge, { toValue: 0.5, duration: 80, useNativeDriver: true }),
      Animated.timing(streamAge, { toValue: 1.0, duration: 200, useNativeDriver: true }),
    ]).start();
  }, [latestFrame?.timestamp]);

  function handleStartStop() {
    if (isStreaming) {
      stopStream();
      setSaved(false);
    } else {
      resetBuffer();
      setSaved(false);
      setSessionStart(Date.now());
      startStream(selectedProfile);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    }
  }

  function handleProfileChange(profile: GaitProfile) {
    setSelectedProfile(profile);
    setProfile(profile);
  }

  async function handleSave() {
    if (!assessment || !metrics) {
      Alert.alert('No Data', 'Start and run a session before saving.');
      return;
    }
    const duration = (Date.now() - sessionStart) / 1000;
    const id = await save(assessment, metrics, 'sensor', duration);
    if (id !== null) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setSaved(true);
      Alert.alert('Saved', `Session #${id} saved to local database.`);
    }
  }

  const lf = latestFrame;

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={[Colors.bgElevated, Colors.bg]} style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Live Dashboard</Text>
          <Text style={styles.headerSub}>Real-time Gait Analysis</Text>
        </View>
        <OfflineIndicator />
      </LinearGradient>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile selector */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>SIMULATION PROFILE</Text>
          <View style={styles.profileRow}>
            {PROFILES.map(p => (
              <TouchableOpacity
                key={p.key}
                style={[
                  styles.profileBtn,
                  selectedProfile === p.key && { borderColor: p.color, backgroundColor: p.color + '22' },
                ]}
                onPress={() => handleProfileChange(p.key)}
                disabled={isStreaming}
              >
                <View style={[styles.profileDot, { backgroundColor: p.color }]} />
                <Text style={[styles.profileLabel, selectedProfile === p.key && { color: p.color }]}>
                  {p.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Stream control */}
        <TouchableOpacity
          style={[styles.streamBtn, isStreaming && styles.streamBtnActive]}
          onPress={handleStartStop}
          activeOpacity={0.8}
        >
          <LinearGradient
            colors={isStreaming
              ? [Colors.riskHigh + 'CC', Colors.riskHigh]
              : [Colors.accent   + 'CC', Colors.accent]}
            style={styles.streamBtnGrad}
          >
            <Ionicons
              name={isStreaming ? 'stop-circle' : 'play-circle'}
              size={24} color="#fff"
            />
            <Text style={styles.streamBtnText}>
              {isStreaming ? 'Stop Session' : 'Start Session'}
            </Text>
            {isStreaming && (
              <Animated.Text style={[styles.frameCount, { opacity: streamAge }]}>
                {frameCount} frames
              </Animated.Text>
            )}
          </LinearGradient>
        </TouchableOpacity>

        {/* Risk assessment card */}
        {assessment && (
          <View style={[styles.card, Shadows.card]}>
            <Text style={styles.sectionLabel}>RISK ASSESSMENT</Text>
            <RiskBadge level={assessment.level} score={assessment.score} />
            {assessment.flaggedMarkers.length > 0 && (
              <View style={styles.flaggedList}>
                <Text style={styles.flaggedTitle}>Flagged Markers</Text>
                {assessment.flaggedMarkers.map(m => (
                  <View key={m.name} style={styles.flaggedItem}>
                    <Ionicons name="warning" size={14} color={Colors.riskMod} />
                    <Text style={styles.flaggedText}>
                      {m.name}: <Text style={{ color: Colors.textPrimary }}>{m.value.toFixed(1)}{m.unit}</Text>
                      <Text style={styles.normalRange}> (Normal: {m.normalRange})</Text>
                    </Text>
                  </View>
                ))}
              </View>
            )}
            <Text style={styles.summaryText}>{assessment.summary}</Text>
          </View>
        )}

        {/* Real-time metrics grid */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>KNEE FLEXION</Text>
          <DualMetricCard
            label="Knee Angle"
            leftValue={lf?.leftKneeAngle   ?? metrics?.leftKneeAngle   ?? 0}
            rightValue={lf?.rightKneeAngle ?? metrics?.rightKneeAngle  ?? 0}
            unit="°"
            normalRange="55–75°"
            accentColor={Colors.metricKnee}
            flagged={(metrics?.kneeAsymmetry ?? 0) > 8}
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionLabel}>FSR PRESSURE DISTRIBUTION</Text>
          <DualMetricCard
            label="Foot Pressure"
            leftValue={lf?.leftFootPressure   ?? metrics?.leftFootPressure   ?? 0}
            rightValue={lf?.rightFootPressure ?? metrics?.rightFootPressure ?? 0}
            unit="%"
            normalRange="Balance < 15% diff"
            accentColor={Colors.metricPressure}
            flagged={(metrics?.pressureAsymmetry ?? 0) > 15}
          />
        </View>

        <View style={[styles.metricsGrid]}>
          <MetricCard
            label="STRIDE ASYMMETRY"
            value={metrics?.strideAsymmetry ?? 0}
            unit="%"
            normalRange="< 5%"
            accentColor={Colors.metricStride}
            flagged={(metrics?.strideAsymmetry ?? 0) > 5}
          />
          <MetricCard
            label="CADENCE"
            value={metrics?.cadenceSPM ?? 0}
            unit="spm"
            normalRange="90–130 spm"
            accentColor={Colors.metricCadence}
          />
        </View>

        <View style={styles.metricsGrid}>
          <MetricCard
            label="HIP SWAY"
            value={metrics?.hipSwayAsymmetry ?? 0}
            unit="%"
            normalRange="< 15%"
            accentColor={Colors.accent}
            flagged={(metrics?.hipSwayAsymmetry ?? 0) > 15}
          />
          <MetricCard
            label="STRIDE CV"
            value={metrics?.strideDurationCV ?? 0}
            unit="%"
            normalRange="< 3%"
            accentColor={Colors.metricKnee}
            flagged={(metrics?.strideDurationCV ?? 0) > 3}
          />
        </View>

        {/* Save button */}
        {metrics && !isStreaming && (
          <TouchableOpacity
            style={[styles.saveBtn, saved && styles.saveBtnDone]}
            onPress={saved ? undefined : handleSave}
            activeOpacity={0.8}
          >
            <Ionicons
              name={saved ? 'checkmark-circle' : 'save-outline'}
              size={20}
              color={saved ? Colors.riskLow : Colors.textInverse}
            />
            <Text style={[styles.saveBtnText, saved && { color: Colors.riskLow }]}>
              {saved ? 'Saved to Local Database' : 'Save Session'}
            </Text>
          </TouchableOpacity>
        )}

        <Text style={styles.disclaimer}>
          For screening purposes only. Not a clinical diagnosis.
          Results must be confirmed by a qualified specialist.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root:    { flex: 1, backgroundColor: Colors.bg },
  header:  {
    flexDirection:  'row',
    alignItems:     'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical:   Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerTitle: {
    fontSize:   Typography.fontSizeXL,
    color:      Colors.textPrimary,
    fontWeight: Typography.fontWeightBold,
  },
  headerSub: {
    fontSize: Typography.fontSizeXS,
    color:    Colors.textSecondary,
    letterSpacing: Typography.letterSpacingWide,
  },
  scroll:         { flex: 1 },
  scrollContent:  { padding: Spacing.md, gap: Spacing.md, paddingBottom: 80 },

  section:       { gap: Spacing.sm },
  sectionLabel:  {
    fontSize:    Typography.fontSizeXS,
    color:       Colors.textMuted,
    letterSpacing: Typography.letterSpacingXWide,
    fontWeight:  Typography.fontWeightSemiBold,
    marginBottom: 2,
  },
  metricsGrid: { flexDirection: 'row', gap: Spacing.sm },

  profileRow: { flexDirection: 'row', gap: Spacing.sm },
  profileBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    padding: Spacing.sm,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgCard,
  },
  profileDot:   { width: 8, height: 8, borderRadius: 4 },
  profileLabel: { fontSize: Typography.fontSizeSM, color: Colors.textSecondary, fontWeight: Typography.fontWeightMedium },

  streamBtn:       { borderRadius: Radius.md, overflow: 'hidden', ...Shadows.glow },
  streamBtnActive: { },
  streamBtnGrad:   {
    flexDirection:  'row',
    alignItems:     'center',
    justifyContent: 'center',
    gap:            Spacing.sm,
    padding:        Spacing.md,
  },
  streamBtnText: { fontSize: Typography.fontSizeLG, color: '#fff', fontWeight: Typography.fontWeightBold },
  frameCount:    { fontSize: Typography.fontSizeXS, color: '#ffffff88', marginLeft: Spacing.sm },

  card: {
    backgroundColor: Colors.bgCard,
    borderRadius:    Radius.md,
    padding:         Spacing.md,
    borderWidth:     1,
    borderColor:     Colors.border,
    gap:             Spacing.md,
  },
  flaggedList:  { gap: Spacing.xs },
  flaggedTitle: { fontSize: Typography.fontSizeXS, color: Colors.textMuted, letterSpacing: Typography.letterSpacingWide },
  flaggedItem:  { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.xs },
  flaggedText:  { fontSize: Typography.fontSizeXS, color: Colors.riskMod, flex: 1 },
  normalRange:  { color: Colors.textMuted },
  summaryText:  { fontSize: Typography.fontSizeSM, color: Colors.textSecondary, lineHeight: 20 },

  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.accent,
    borderRadius: Radius.md,
    padding: Spacing.md,
    ...Shadows.glow,
  },
  saveBtnDone: { backgroundColor: Colors.bgCard, borderWidth: 1, borderColor: Colors.riskLow },
  saveBtnText: { fontSize: Typography.fontSizeMD, color: Colors.textInverse, fontWeight: Typography.fontWeightBold },

  disclaimer: {
    fontSize:  Typography.fontSizeXS,
    color:     Colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    paddingHorizontal: Spacing.md,
  },
});
