// src/screens/HistoryScreen.tsx
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, FlatList, StyleSheet, Modal,
  TouchableOpacity, ScrollView, Alert, RefreshControl,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SessionCard } from '../components/SessionCard';
import { RiskBadge } from '../components/RiskBadge';
import { MetricCard, DualMetricCard } from '../components/MetricCard';
import { OfflineIndicator } from '../components/OfflineIndicator';
import { useDatabase } from '../hooks/useDatabase';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import type { ScreeningSession } from '../types';

export function HistoryScreen() {
  const { sessions, loading, error, loadSessions, remove } = useDatabase();
  const [selected, setSelected] = useState<ScreeningSession | null>(null);

  useEffect(() => { loadSessions(); }, []);

  const onDelete = useCallback((id: number) => {
    Alert.alert('Delete Session', `Remove session #${id} from local storage?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => remove(id) },
    ]);
  }, [remove]);

  const totalSessions  = sessions.length;
  const highRiskCount  = sessions.filter(s => s.riskLevel === 'High Risk / Potential OA').length;
  const avgScore       = sessions.length > 0
    ? (sessions.reduce((a, b) => a + b.riskScore, 0) / sessions.length).toFixed(1)
    : '—';

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={[Colors.bgElevated, Colors.bg]} style={styles.header}>
        <View>
          <Text style={styles.title}>Session History</Text>
          <Text style={styles.subtitle}>Local SQLite Storage</Text>
        </View>
        <OfflineIndicator />
      </LinearGradient>

      {/* Summary stats */}
      <View style={styles.statsRow}>
        <StatPill icon="layers"      label="Total"    value={String(totalSessions)} color={Colors.accent} />
        <StatPill icon="alert-circle" label="High Risk" value={String(highRiskCount)} color={Colors.riskHigh} />
        <StatPill icon="stats-chart" label="Avg Score" value={avgScore}              color={Colors.riskMod} />
      </View>

      {/* List */}
      {error ? (
        <View style={styles.centred}>
          <Ionicons name="warning-outline" size={48} color={Colors.riskHigh} />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={loadSessions} style={styles.retryBtn}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : sessions.length === 0 && !loading ? (
        <View style={styles.centred}>
          <Ionicons name="file-tray-outline" size={64} color={Colors.textMuted} />
          <Text style={styles.emptyTitle}>No sessions yet</Text>
          <Text style={styles.emptyBody}>
            Complete a Camera Screening or Dashboard session to save your first record.
          </Text>
        </View>
      ) : (
        <FlatList
          data={sessions}
          keyExtractor={s => String(s.id)}
          renderItem={({ item }) => (
            <SessionCard
              session={item}
              onPress={() => setSelected(item)}
              onDelete={() => onDelete(item.id)}
            />
          )}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={loadSessions}
              tintColor={Colors.accent}
            />
          }
        />
      )}

      {/* Detail Modal */}
      <Modal
        visible={!!selected}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setSelected(null)}
      >
        {selected && (
          <SafeAreaView style={styles.modalRoot} edges={['top', 'bottom']}>
            {/* Modal header */}
            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setSelected(null)} style={styles.modalClose}>
                <Ionicons name="close" size={24} color={Colors.textPrimary} />
              </TouchableOpacity>
              <Text style={styles.modalTitle}>Session #{selected.id}</Text>
              <TouchableOpacity onPress={() => { onDelete(selected.id); setSelected(null); }}>
                <Ionicons name="trash-outline" size={20} color={Colors.riskHigh} />
              </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.modalContent}>
              {/* Date / duration */}
              <View style={styles.detailMeta}>
                <View style={styles.detailMetaItem}>
                  <Ionicons name="calendar-outline" size={14} color={Colors.textMuted} />
                  <Text style={styles.detailMetaText}>
                    {new Date(selected.timestamp).toLocaleString('en-IN')}
                  </Text>
                </View>
                <View style={styles.detailMetaItem}>
                  <Ionicons name="timer-outline" size={14} color={Colors.textMuted} />
                  <Text style={styles.detailMetaText}>
                    {selected.durationSeconds.toFixed(0)}s • {selected.mode}
                  </Text>
                </View>
              </View>

              {/* Risk badge */}
              <RiskBadge level={selected.riskLevel} score={selected.riskScore} />

              {/* Summary */}
              <View style={styles.summaryBox}>
                <Text style={styles.summaryText}>{selected.summary}</Text>
              </View>

              {/* Metrics */}
              <Text style={styles.metricSectionLabel}>KNEE METRICS</Text>
              <DualMetricCard
                label="Knee Flexion Angle"
                leftValue={selected.metrics.leftKneeAngle}
                rightValue={selected.metrics.rightKneeAngle}
                unit="°" normalRange="55–75°"
                accentColor={Colors.metricKnee}
              />
              <DualMetricCard
                label="Knee ROM"
                leftValue={selected.metrics.leftKneeROM}
                rightValue={selected.metrics.rightKneeROM}
                unit="°" normalRange="55–75°"
                accentColor={Colors.metricKnee}
              />

              <Text style={styles.metricSectionLabel}>PRESSURE (FSR)</Text>
              <DualMetricCard
                label="Foot Pressure Distribution"
                leftValue={selected.metrics.leftFootPressure}
                rightValue={selected.metrics.rightFootPressure}
                unit="%" normalRange="Balance < 15% diff"
                accentColor={Colors.metricPressure}
              />

              <Text style={styles.metricSectionLabel}>GAIT PARAMETERS</Text>
              <View style={styles.detailGrid}>
                <MetricCard label="CADENCE"        value={selected.metrics.cadenceSPM}       unit="spm" normalRange="90–130 spm" accentColor={Colors.metricCadence} />
                <MetricCard label="STRIDE ASYM"    value={selected.metrics.strideAsymmetry}  unit="%"   normalRange="< 5%"       accentColor={Colors.metricStride}  />
              </View>
              <View style={styles.detailGrid}>
                <MetricCard label="HIP SWAY"       value={selected.metrics.hipSwayAsymmetry} unit="%"   normalRange="< 15%"      accentColor={Colors.accent}        />
                <MetricCard label="STRIDE CV"      value={selected.metrics.strideDurationCV} unit="%"   normalRange="< 3%"       accentColor={Colors.metricKnee}    />
              </View>
              <View style={styles.detailGrid}>
                <MetricCard label="L STANCE RATIO" value={selected.metrics.leftStanceRatio  * 100} unit="%" normalRange="60–65%" accentColor={Colors.metricStride} />
                <MetricCard label="R STANCE RATIO" value={selected.metrics.rightStanceRatio * 100} unit="%" normalRange="60–65%" accentColor={Colors.metricStride} />
              </View>

              <Text style={styles.disclaimerText}>
                For screening purposes only. Not a clinical diagnosis.
              </Text>
            </ScrollView>
          </SafeAreaView>
        )}
      </Modal>
    </SafeAreaView>
  );
}

function StatPill({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  return (
    <View style={[styles.statPill, { borderColor: color + '44' }]}>
      <Ionicons name={icon as any} size={14} color={color} />
      <Text style={[styles.statVal, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.bg },

  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  title:    { fontSize: Typography.fontSizeXL,  color: Colors.textPrimary, fontWeight: Typography.fontWeightBold },
  subtitle: { fontSize: Typography.fontSizeXS,  color: Colors.textSecondary, letterSpacing: Typography.letterSpacingWide },

  statsRow: { flexDirection: 'row', gap: Spacing.sm, paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md },
  statPill: {
    flex: 1, flexDirection: 'column', alignItems: 'center', gap: 2,
    borderWidth: 1, borderRadius: Radius.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.bgCard,
  },
  statVal:   { fontSize: Typography.fontSizeLG, fontWeight: Typography.fontWeightBold },
  statLabel: { fontSize: Typography.fontSizeXS, color: Colors.textMuted },

  listContent: { paddingHorizontal: Spacing.lg, paddingBottom: 80 },

  centred: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: Spacing.md, padding: Spacing.xl },
  errorText:  { fontSize: Typography.fontSizeMD, color: Colors.riskHigh, textAlign: 'center' },
  retryBtn:   { backgroundColor: Colors.accent, paddingHorizontal: Spacing.xl, paddingVertical: Spacing.sm, borderRadius: Radius.full },
  retryText:  { color: Colors.textInverse, fontWeight: Typography.fontWeightBold },
  emptyTitle: { fontSize: Typography.fontSizeLG,  color: Colors.textSecondary, fontWeight: Typography.fontWeightSemiBold },
  emptyBody:  { fontSize: Typography.fontSizeSM,  color: Colors.textMuted, textAlign: 'center', lineHeight: 22 },

  // Modal
  modalRoot:    { flex: 1, backgroundColor: Colors.bg },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  modalClose:  { width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.bgElevated, alignItems: 'center', justifyContent: 'center' },
  modalTitle:  { fontSize: Typography.fontSizeLG, color: Colors.textPrimary, fontWeight: Typography.fontWeightBold },
  modalContent:{ padding: Spacing.lg, gap: Spacing.md, paddingBottom: 60 },

  detailMeta: { gap: Spacing.xs },
  detailMetaItem: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  detailMetaText: { fontSize: Typography.fontSizeSM, color: Colors.textSecondary },

  summaryBox: {
    backgroundColor: Colors.bgElevated, borderRadius: Radius.md,
    padding: Spacing.md, borderWidth: 1, borderColor: Colors.border,
  },
  summaryText: { fontSize: Typography.fontSizeSM, color: Colors.textSecondary, lineHeight: 22 },

  metricSectionLabel: {
    fontSize: Typography.fontSizeXS, color: Colors.textMuted,
    letterSpacing: Typography.letterSpacingXWide, fontWeight: Typography.fontWeightSemiBold,
    marginTop: Spacing.sm,
  },
  detailGrid:       { flexDirection: 'row', gap: Spacing.sm },
  disclaimerText:   { fontSize: Typography.fontSizeXS, color: Colors.textMuted, textAlign: 'center', lineHeight: 18, marginTop: Spacing.md },
});
