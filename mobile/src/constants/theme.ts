import '@/global.css';

import { Platform, type ColorValue, type TextStyle } from 'react-native';

const pitch = {
  text: '#F3F1EC',
  textSecondary: '#8C8880',
  background: '#0B0C0E',
  backgroundElement: '#16181C',
  backgroundSelected: '#22252B',
  separator: 'rgba(243,241,236,0.12)',
  accent: '#C8F54A',
  onAccent: '#14160A',
  positive: '#C8F54A',
  danger: '#FF6B4A',
} as const;

export type ThemeColor = keyof typeof pitch;

export function palette(_scheme: 'light' | 'dark'): Record<ThemeColor, ColorValue> {
  return pitch;
}

export function statusInk(
  status: string,
  theme: Pick<Record<ThemeColor, ColorValue>, 'positive' | 'danger' | 'textSecondary'>,
): ColorValue {
  if (status === 'done') return theme.positive;
  if (status === 'error') return theme.danger;
  return theme.textSecondary;
}

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  full: 999,
} as const;

export const Type = {
  largeTitle: { fontSize: 34, lineHeight: 41, fontWeight: '700', letterSpacing: -0.4 },
  title: { fontSize: 22, lineHeight: 28, fontWeight: '600', letterSpacing: -0.3 },
  headline: { fontSize: 17, lineHeight: 22, fontWeight: '600' },
  body: { fontSize: 17, lineHeight: 24, fontWeight: '400' },
  subhead: { fontSize: 15, lineHeight: 20, fontWeight: '400' },
  footnote: { fontSize: 13, lineHeight: 18, fontWeight: '400' },
  footnoteBold: { fontSize: 13, lineHeight: 18, fontWeight: '600' },
} as const satisfies Record<string, TextStyle>;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const PhoneWidth = 402;

export const webCursor = process.env.EXPO_OS === 'web' ? ({ cursor: 'pointer' } as const) : undefined;
