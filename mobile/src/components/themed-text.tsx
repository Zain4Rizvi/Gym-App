import { Platform, StyleSheet, Text, type TextProps } from 'react-native';

import { Fonts, Type, type ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export type ThemedTextProps = TextProps & {
  type?: 'default' | 'title' | 'small' | 'smallBold' | 'subtitle' | 'link' | 'linkPrimary' | 'headline' | 'code';
  themeColor?: ThemeColor;
};

export function ThemedText({ style, type = 'default', themeColor, ...rest }: ThemedTextProps) {
  const theme = useTheme();
  const color =
    type === 'link' || type === 'linkPrimary'
      ? theme.accent
      : theme[themeColor ?? 'text'];

  return <Text style={[{ color }, styles[type], style]} {...rest} />;
}

const styles = StyleSheet.create({
  small: Type.footnote,
  smallBold: Type.footnoteBold,
  default: Type.body,
  headline: Type.headline,
  title: Type.largeTitle,
  subtitle: Type.title,
  link: Type.headline,
  linkPrimary: Type.headline,
  code: {
    fontFamily: Fonts.mono,
    fontWeight: Platform.select({ android: '700' }) ?? '500',
    fontSize: 12,
    lineHeight: 16,
  },
});
