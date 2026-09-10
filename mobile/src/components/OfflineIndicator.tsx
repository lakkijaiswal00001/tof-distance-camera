// src/components/OfflineIndicator.tsx
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import * as Network from 'expo-network';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Typography, Spacing, Radius } from '../theme';

export function OfflineIndicator() {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const pulse = new Animated.Value(1);

  useEffect(() => {
    const check = async () => {
      const state = await Network.getNetworkStateAsync();
      setIsConnected(state.isConnected ?? false);
    };
    check();
    const interval = setInterval(check, 8000);
    return () => clearInterval(interval);
  }, []);

  // Pulse animation for offline state
  useEffect(() => {
    if (isConnected === false) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 0.4, duration: 900, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1.0, duration: 900, useNativeDriver: true }),
        ])
      ).start();
    }
  }, [isConnected]);

  const label  = isConnected ? 'ONLINE'  : 'OFFLINE — LOCAL MODE';
  const color  = isConnected ? Colors.online : Colors.offline;
  const icon   = isConnected ? 'wifi'    : 'cloud-offline-outline';

  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <Animated.View style={[styles.dot, { backgroundColor: color, opacity: isConnected ? 1 : pulse }]} />
      <Ionicons name={icon as any} size={11} color={color} style={{ marginRight: 4 }} />
      <Text style={[styles.label, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection:   'row',
    alignItems:      'center',
    paddingHorizontal: Spacing.sm,
    paddingVertical:   3,
    borderRadius:    Radius.full,
    borderWidth:     1,
    backgroundColor: Colors.bgCard,
  },
  dot: {
    width: 6, height: 6,
    borderRadius: 3,
    marginRight: 5,
  },
  label: {
    fontSize:    Typography.fontSizeXS,
    fontWeight:  Typography.fontWeightSemiBold,
    letterSpacing: Typography.letterSpacingXWide,
  },
});
