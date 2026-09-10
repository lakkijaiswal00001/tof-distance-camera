// src/theme/index.ts
// ─────────────────────────────────────────────────────────────────────────────
// Global design tokens — dark medical-grade palette
// ─────────────────────────────────────────────────────────────────────────────

export const Colors = {
  // Backgrounds
  bg:          '#0A0E1A',   // deep navy — primary background
  bgCard:      '#121826',   // card surface
  bgElevated:  '#1A2235',   // raised panel
  bgInput:     '#1E293B',   // input fields

  // Brand / Accent
  accent:      '#00E5C8',   // teal — primary accent
  accentDim:   '#00B09E',   // muted teal
  accentGlow:  'rgba(0, 229, 200, 0.15)',

  // Risk colours
  riskLow:     '#00C853',   // green
  riskMod:     '#FFB300',   // amber
  riskHigh:    '#FF3D3D',   // red

  // Status
  online:      '#00C853',
  offline:     '#FF3D3D',

  // Text
  textPrimary:   '#E8ECF4',
  textSecondary: '#8899B4',
  textMuted:     '#4A5568',
  textInverse:   '#0A0E1A',

  // Borders / Dividers
  border:      '#1E2D45',
  divider:     '#162030',

  // Sensor metrics
  metricKnee:    '#00E5C8',
  metricPressure:'#7C4DFF',
  metricStride:  '#FF6B35',
  metricCadence: '#00BCD4',

  // Overlays
  overlay:     'rgba(10, 14, 26, 0.75)',
  overlayLight:'rgba(10, 14, 26, 0.45)',
} as const;

export const Typography = {
  fontSizeXS:  11,
  fontSizeSM:  13,
  fontSizeMD:  15,
  fontSizeLG:  18,
  fontSizeXL:  22,
  fontSizeXXL: 28,
  fontSizeHero:36,

  fontWeightRegular:  '400' as const,
  fontWeightMedium:   '500' as const,
  fontWeightSemiBold: '600' as const,
  fontWeightBold:     '700' as const,
  fontWeightHeavy:    '800' as const,

  letterSpacingTight:  -0.5,
  letterSpacingNormal:  0,
  letterSpacingWide:    0.8,
  letterSpacingXWide:   2.0,
} as const;

export const Spacing = {
  xs:  4,
  sm:  8,
  md:  16,
  lg:  24,
  xl:  32,
  xxl: 48,
} as const;

export const Radius = {
  sm:   8,
  md:   12,
  lg:   16,
  xl:   24,
  full: 999,
} as const;

export const Shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  glow: {
    shadowColor: '#00E5C8',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 8,
  },
} as const;
