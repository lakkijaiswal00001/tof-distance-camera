// src/screens/CameraScreen.tsx
import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet,
  Alert, Dimensions, Platform,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AlignmentGuide } from '../components/AlignmentGuide';
import { OfflineIndicator } from '../components/OfflineIndicator';
import { Colors, Typography, Spacing, Radius, Shadows } from '../theme';
import type { StackNavigationProp } from '@react-navigation/stack';

const { width: W } = Dimensions.get('window');

type AlignStatus = 'scanning' | 'partial' | 'ready';

interface Props {
  navigation: StackNavigationProp<any>;
}

// Simulated alignment progression (in real app: use pose estimation on device)
const ALIGN_MESSAGES: Record<AlignStatus, string> = {
  scanning: 'Scanning for your body… Step into the frame.',
  partial:  'Hold still — partial body detected. Ensure head & feet are visible.',
  ready:    'Great position! Hold still — recording will begin.',
};

export function CameraScreen({ navigation }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [facing,     setFacing]         = useState<'front' | 'back'>('back');
  const [alignStatus, setAlignStatus]   = useState<AlignStatus>('scanning');
  const [isRecording,  setIsRecording]  = useState(false);
  const [elapsed,      setElapsed]      = useState(0);
  const [stableCount,  setStableCount]  = useState(0);

  const timerRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const alignTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Simulate alignment detection ───────────────────────────────────────────
  useEffect(() => {
    if (isRecording) return;
    // Simulate detection phases
    alignTimer.current = setInterval(() => {
      setStableCount(c => {
        const next = c + 1;
        if (next < 3)        setAlignStatus('scanning');
        else if (next < 8)   setAlignStatus('partial');
        else                 setAlignStatus('ready');
        return next;
      });
    }, 700);
    return () => { if (alignTimer.current) clearInterval(alignTimer.current); };
  }, [isRecording]);

  // ── Recording timer ────────────────────────────────────────────────────────
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsed(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isRecording]);

  // ── Permission guard ───────────────────────────────────────────────────────
  if (!permission) return <View style={styles.root} />;

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.root}>
        <LinearGradient colors={[Colors.bg, '#0D1528']} style={styles.permScreen}>
          <Ionicons name="camera-outline" size={64} color={Colors.accent} />
          <Text style={styles.permTitle}>Camera Access Needed</Text>
          <Text style={styles.permBody}>
            The OA screening tool needs camera access to record your walking gait for analysis.
          </Text>
          <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
            <Text style={styles.permBtnText}>Grant Permission</Text>
          </TouchableOpacity>
        </LinearGradient>
      </SafeAreaView>
    );
  }

  // ── Handlers ───────────────────────────────────────────────────────────────
  function handleStartRecording() {
    if (alignStatus !== 'ready') {
      Alert.alert('Not Aligned', 'Please position yourself within the guide frame first.');
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    setIsRecording(true);
  }

  function handleStopRecording() {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setIsRecording(false);
    // Navigate to Dashboard for results
    navigation.navigate('Dashboard');
  }

  function handleFlipCamera() {
    Haptics.selectionAsync();
    setFacing(f => f === 'back' ? 'front' : 'back');
  }

  const recColor = isRecording ? Colors.riskHigh : Colors.accent;

  return (
    <View style={styles.root}>
      {/* Camera preview */}
      <CameraView style={StyleSheet.absoluteFill} facing={facing} />

      {/* Alignment guide overlay */}
      {!isRecording && (
        <AlignmentGuide
          status={alignStatus}
          message={ALIGN_MESSAGES[alignStatus]}
        />
      )}

      {/* Recording pulse overlay */}
      {isRecording && (
        <View style={styles.recOverlay} pointerEvents="none">
          <View style={styles.recDot} />
          <Text style={styles.recLabel}>REC  {String(Math.floor(elapsed / 60)).padStart(2,'0')}:{String(elapsed % 60).padStart(2,'0')}</Text>
        </View>
      )}

      {/* Top bar */}
      <SafeAreaView edges={['top']} style={styles.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
        <OfflineIndicator />
        <TouchableOpacity onPress={handleFlipCamera} style={styles.iconBtn}>
          <Ionicons name="camera-reverse-outline" size={24} color={Colors.textPrimary} />
        </TouchableOpacity>
      </SafeAreaView>

      {/* Bottom controls */}
      <SafeAreaView edges={['bottom']} style={styles.bottomBar}>
        <LinearGradient
          colors={['transparent', 'rgba(10,14,26,0.92)']}
          style={styles.bottomGradient}
        >
          {/* Instruction */}
          {!isRecording && (
            <Text style={styles.instruction}>
              {alignStatus === 'ready'
                ? 'Walk naturally sideways or toward the camera for 10–15 seconds'
                : 'Position yourself within the guide frame'}
            </Text>
          )}

          {/* Record button */}
          <TouchableOpacity
            style={[
              styles.recordBtn,
              { borderColor: recColor },
              isRecording && styles.recordBtnActive,
            ]}
            onPress={isRecording ? handleStopRecording : handleStartRecording}
            activeOpacity={0.8}
          >
            <View style={[styles.recordInner, { backgroundColor: recColor }]}>
              {isRecording
                ? <Ionicons name="stop" size={28} color="#fff" />
                : <Ionicons name="radio-button-on" size={32} color="#fff" />}
            </View>
          </TouchableOpacity>

          <Text style={styles.recordHint}>
            {isRecording ? 'Tap to stop and analyse' : 'Tap to start recording'}
          </Text>
        </LinearGradient>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root:     { flex: 1, backgroundColor: '#000' },
  topBar: {
    position:      'absolute',
    top: 0, left: 0, right: 0,
    flexDirection: 'row',
    alignItems:    'center',
    justifyContent:'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical:   Spacing.sm,
  },
  iconBtn: {
    width: 40, height: 40,
    borderRadius: 20,
    backgroundColor: Colors.overlay,
    alignItems: 'center', justifyContent: 'center',
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0, left: 0, right: 0,
  },
  bottomGradient: {
    alignItems: 'center',
    paddingBottom: Spacing.xxl,
    paddingTop: Spacing.xl,
  },
  instruction: {
    fontSize:   Typography.fontSizeSM,
    color:      Colors.textSecondary,
    textAlign:  'center',
    marginBottom: Spacing.lg,
    paddingHorizontal: Spacing.xl,
  },
  recordBtn: {
    width:  80, height: 80,
    borderRadius: 40,
    borderWidth:  3,
    alignItems:   'center',
    justifyContent: 'center',
    backgroundColor: Colors.overlay,
  },
  recordBtnActive: { backgroundColor: 'rgba(255,60,60,0.15)' },
  recordInner: {
    width:  60, height: 60,
    borderRadius: 30,
    alignItems: 'center', justifyContent: 'center',
  },
  recordHint: {
    marginTop:  Spacing.md,
    fontSize:   Typography.fontSizeXS,
    color:      Colors.textMuted,
    letterSpacing: Typography.letterSpacingWide,
  },
  // Recording overlay
  recOverlay: {
    position:      'absolute',
    top:           80,
    left:          Spacing.md,
    flexDirection: 'row',
    alignItems:    'center',
    gap:           Spacing.sm,
    backgroundColor: Colors.overlay,
    borderRadius:  Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical:   Spacing.xs,
  },
  recDot: {
    width: 10, height: 10, borderRadius: 5,
    backgroundColor: Colors.riskHigh,
  },
  recLabel: {
    fontSize:   Typography.fontSizeSM,
    color:      Colors.riskHigh,
    fontWeight: Typography.fontWeightBold,
    letterSpacing: Typography.letterSpacingWide,
  },
  // Permission
  permScreen: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: Spacing.xl, gap: Spacing.lg,
  },
  permTitle: {
    fontSize:   Typography.fontSizeXL,
    color:      Colors.textPrimary,
    fontWeight: Typography.fontWeightBold,
    textAlign:  'center',
  },
  permBody: {
    fontSize:  Typography.fontSizeMD,
    color:     Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
  },
  permBtn: {
    backgroundColor: Colors.accent,
    paddingHorizontal: Spacing.xl,
    paddingVertical:   Spacing.md,
    borderRadius:      Radius.full,
    marginTop:         Spacing.md,
  },
  permBtnText: {
    fontSize:   Typography.fontSizeMD,
    color:      Colors.textInverse,
    fontWeight: Typography.fontWeightBold,
  },
});
