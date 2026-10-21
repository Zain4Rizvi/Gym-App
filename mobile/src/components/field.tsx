import { TextInput, type TextInputProps } from "react-native";

import { ThemedText } from "@/components/themed-text";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export function Field({
  label,
  ...props
}: TextInputProps & { label: string }) {
  const theme = useTheme();
  return (
    <>
      <ThemedText type="small">{label}</ThemedText>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.textSecondary}
        style={{
          color: theme.text,
          backgroundColor: theme.backgroundElement,
          borderRadius: Spacing.two,
          padding: Spacing.three,
          fontSize: 16,
        }}
        {...props}
      />
    </>
  );
}
