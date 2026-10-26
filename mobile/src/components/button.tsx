import { Pressable, type StyleProp, type ViewStyle } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing, webCursor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Button({
  title,
  onPress,
  disabled,
  variant = 'primary',
  style,
}: {
  title: string;
  onPress?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'destructive';
  style?: StyleProp<ViewStyle>;
}) {
  const theme = useTheme();
  const filled = variant === 'primary';
  const color = disabled
    ? theme.textSecondary
    : filled
      ? theme.onAccent
      : variant === 'destructive'
        ? theme.danger
        : theme.text;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        {
          minHeight: 48,
          paddingHorizontal: filled ? Spacing.three : 0,
          alignItems: filled ? 'center' : 'flex-start',
          justifyContent: 'center',
          borderRadius: filled ? Radius.md : 0,
          borderCurve: 'continuous',
          backgroundColor: filled ? (disabled ? theme.backgroundSelected : theme.accent) : 'transparent',
          opacity: pressed && !disabled ? 0.7 : 1,
        },
        webCursor,
        style,
      ]}>
      <ThemedText type="headline" style={{ color }}>
        {title}
      </ThemedText>
    </Pressable>
  );
}
