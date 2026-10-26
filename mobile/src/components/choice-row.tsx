import { Pressable, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing, webCursor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function ChoiceRow({
  options,
  value,
  onChange,
}: {
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
}) {
  const theme = useTheme();
  const segmented = options.length > 0 && options.length <= 5;

  if (segmented) {
    return (
      <View
        style={{
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: 2,
          padding: 2,
          backgroundColor: theme.backgroundSelected,
          borderRadius: Radius.md,
          borderCurve: 'continuous',
        }}>
        {options.map((option) => {
          const selected = option === value;
          return (
            <Pressable
              key={option}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => onChange(option)}
              style={({ pressed }) => [
                {
                  flexGrow: 1,
                  minWidth: 72,
                  minHeight: 44,
                  paddingHorizontal: Spacing.two,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: Radius.sm,
                  borderCurve: 'continuous',
                  backgroundColor: selected ? theme.backgroundElement : pressed ? theme.background : 'transparent',
                },
                webCursor,
              ]}>
              <ThemedText type="smallBold" style={{ color: selected ? theme.accent : theme.text }}>
                {option}
              </ThemedText>
            </Pressable>
          );
        })}
      </View>
    );
  }

  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two }}>
      {options.map((option) => {
        const selected = option === value;
        return (
          <Pressable
            key={option}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => onChange(option)}
            style={({ pressed }) => [
              {
                minHeight: 44,
                paddingHorizontal: Spacing.three,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: Radius.md,
                borderCurve: 'continuous',
                backgroundColor: selected ? theme.accent : pressed ? theme.backgroundSelected : theme.backgroundElement,
              },
              webCursor,
            ]}>
            <ThemedText type="smallBold" style={{ color: selected ? theme.onAccent : theme.text }}>
              {option}
            </ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}
