import { StyleSheet, TextInput, View, type TextInputProps } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Field({
  label,
  inline = false,
  grouped = false,
  ruled = true,
  style,
  ...props
}: TextInputProps & {
  label: string;
  inline?: boolean;
  grouped?: boolean;
  ruled?: boolean;
}) {
  const theme = useTheme();
  const numeric = props.keyboardType === 'decimal-pad' || props.keyboardType === 'number-pad';
  const multiline = !!props.multiline;

  return (
    <View
      style={[
        grouped
          ? {
              borderBottomWidth: ruled ? StyleSheet.hairlineWidth : 0,
              borderBottomColor: theme.separator,
              paddingHorizontal: Spacing.three,
            }
          : {
              backgroundColor: theme.backgroundElement,
              borderRadius: Radius.lg,
              borderCurve: 'continuous',
              paddingHorizontal: Spacing.three,
            },
      ]}>
      {inline && !multiline ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.three, minHeight: 48 }}>
          <ThemedText style={{ flexShrink: 0 }}>{label}</ThemedText>
          <TextInput
            accessibilityLabel={label}
            placeholderTextColor={theme.textSecondary}
            style={[
              {
                flex: 1,
                minWidth: 72,
                color: theme.text,
                fontSize: 17,
                lineHeight: 22,
                textAlign: 'right',
                fontVariant: numeric ? ['tabular-nums'] : undefined,
                paddingVertical: Spacing.two,
              },
              style,
            ]}
            {...props}
          />
        </View>
      ) : (
        <View style={{ gap: Spacing.one, paddingVertical: Spacing.two }}>
          <ThemedText type="small" themeColor="textSecondary">
            {label}
          </ThemedText>
          <TextInput
            accessibilityLabel={label}
            placeholderTextColor={theme.textSecondary}
            style={[
              {
                color: theme.text,
                fontSize: 17,
                lineHeight: 24,
                minHeight: multiline ? 120 : 32,
                textAlignVertical: multiline ? 'top' : 'center',
                fontVariant: numeric ? ['tabular-nums'] : undefined,
              },
              style,
            ]}
            {...props}
          />
        </View>
      )}
    </View>
  );
}
