// src/navigation/AppNavigator.tsx
import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';

import { HomeScreen }      from '../screens/HomeScreen';
import { CameraScreen }    from '../screens/CameraScreen';
import { DashboardScreen } from '../screens/DashboardScreen';
import { HistoryScreen }   from '../screens/HistoryScreen';

import { Colors, Typography, Spacing, Radius } from '../theme';
import type { RootTabParamList } from '../types';

const Tab   = createBottomTabNavigator<RootTabParamList>();
const Stack = createStackNavigator();

type TabConfig = {
  name:  keyof RootTabParamList;
  icon:  string;
  label: string;
};

const TABS: TabConfig[] = [
  { name: 'Home',      icon: 'home',        label: 'Home'      },
  { name: 'Camera',    icon: 'videocam',    label: 'Camera'    },
  { name: 'Dashboard', icon: 'pulse',       label: 'Dashboard' },
  { name: 'History',   icon: 'time',        label: 'History'   },
];

function TabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarBackground: () =>
          Platform.OS === 'ios' ? (
            <BlurView intensity={80} tint="dark" style={StyleSheet.absoluteFill} />
          ) : (
            <View style={[StyleSheet.absoluteFill, styles.tabBarBg]} />
          ),
        tabBarShowLabel: true,
        tabBarLabelStyle: styles.tabLabel,
        tabBarActiveTintColor:   Colors.accent,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarIcon: ({ focused, color, size }) => {
          const tab  = TABS.find(t => t.name === route.name)!;
          const icon = focused ? tab.icon : `${tab.icon}-outline`;
          return (
            <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
              <Ionicons name={icon as any} size={22} color={color} />
            </View>
          );
        },
      })}
    >
      {TABS.map(tab => (
        <Tab.Screen
          key={tab.name}
          name={tab.name}
          options={{ tabBarLabel: tab.label }}
          component={
            tab.name === 'Home'      ? HomeScreen      :
            tab.name === 'Camera'   ? CameraScreen    :
            tab.name === 'Dashboard'? DashboardScreen :
            HistoryScreen
          }
        />
      ))}
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  return (
    <NavigationContainer
      theme={{
        dark: true,
        colors: {
          primary:    Colors.accent,
          background: Colors.bg,
          card:       Colors.bgCard,
          text:       Colors.textPrimary,
          border:     Colors.border,
          notification: Colors.riskHigh,
        },
      }}
    >
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Main" component={TabNavigator} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    position:      'absolute',
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    height:         Platform.OS === 'ios' ? 88 : 64,
    paddingBottom:  Platform.OS === 'ios' ? 24 : 8,
    backgroundColor: 'transparent',
    elevation: 0,
  },
  tabBarBg: {
    backgroundColor: Colors.bgElevated,
    opacity: 0.97,
  },
  tabLabel: {
    fontSize:     Typography.fontSizeXS,
    fontWeight:   Typography.fontWeightSemiBold,
    letterSpacing: 0.5,
    marginTop:    2,
  },
  iconWrap: {
    width:  36, height: 36,
    borderRadius: 10,
    alignItems:   'center',
    justifyContent: 'center',
  },
  iconWrapActive: {
    backgroundColor: Colors.accentGlow,
  },
});
