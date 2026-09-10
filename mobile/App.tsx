// App.tsx — root entry point
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppNavigator } from './src/navigation/AppNavigator';
import { openDatabase } from './src/services/database';
import { Colors, Typography, Spacing } from './src/theme';

type InitState = 'loading' | 'ready' | 'error';

export default function App() {
  const [initState, setInitState] = useState<InitState>('loading');
  const [error,     setError]     = useState<string>('');

  useEffect(() => {
    openDatabase()
      .then(() => setInitState('ready'))
      .catch((err: any) => {
        console.error('[App] DB init failed:', err);
        setError(err?.message ?? 'Failed to initialise local database.');
        setInitState('error');
      });
  }, []);

  if (initState === 'loading') {
    return (
      <View style={styles.splash}>
        <StatusBar style="light" />
        <ActivityIndicator size="large" color={Colors.accent} />
        <Text style={styles.splashText}>Initialising OA Gait Screener…</Text>
        <Text style={styles.splashSub}>Setting up local database</Text>
      </View>
    );
  }

  if (initState === 'error') {
    return (
      <View style={styles.splash}>
        <StatusBar style="light" />
        <Text style={styles.errorTitle}>⚠ Setup Error</Text>
        <Text style={styles.errorMsg}>{error}</Text>
        <Text style={styles.splashSub}>
          Try restarting the app. If the problem persists, reinstall.
        </Text>
      </View>
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style="light" backgroundColor={Colors.bg} />
        <AppNavigator />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    backgroundColor: Colors.bg,
    alignItems:      'center',
    justifyContent:  'center',
    gap:             Spacing.md,
    padding:         Spacing.xl,
  },
  splashText: {
    fontSize:   Typography.fontSizeLG,
    color:      Colors.textPrimary,
    fontWeight: Typography.fontWeightSemiBold,
    textAlign:  'center',
  },
  splashSub: {
    fontSize: Typography.fontSizeSM,
    color:    Colors.textMuted,
    textAlign:'center',
  },
  errorTitle: {
    fontSize:   Typography.fontSizeXL,
    color:      Colors.riskHigh,
    fontWeight: Typography.fontWeightBold,
    textAlign:  'center',
  },
  errorMsg: {
    fontSize:  Typography.fontSizeMD,
    color:     Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
  },
});
