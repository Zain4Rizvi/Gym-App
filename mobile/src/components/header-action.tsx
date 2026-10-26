import { Pressable } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { webCursor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function HeaderAction({
  label,
  onPress,
  disabled,
  commit = false,
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  commit?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      disabled={disabled}
      hitSlop={12}
      onPress={onPress}
      style={({ pressed }) => [
        commit
          ? {
              minHeight: 32,
              paddingHorizontal: 12,
              borderRadius: 8,
              borderCurve: 'continuous',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: disabled ? theme.backgroundSelected : theme.accent,
              opacity: pressed && !disabled ? 0.75 : 1,
            }
          : { opacity: disabled ? 0.4 : pressed ? 0.55 : 1, paddingHorizontal: 4 },
        webCursor,
      ]}>
      <ThemedText
        type={commit ? 'smallBold' : 'headline'}
        style={{ color: commit ? (disabled ? theme.textSecondary : theme.onAccent) : theme.text }}>
        {label}
      </ThemedText>
    </Pressable>
  );
}
