import { Pressable, View } from "react-native";

import { ThemedText } from "@/components/themed-text";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

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
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Spacing.two }}>
      {options.map((option) => {
        const selected = option === value;
        return (
          <Pressable
            key={option}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => onChange(option)}
            style={{
              paddingVertical: Spacing.two,
              paddingHorizontal: Spacing.three,
              borderRadius: Spacing.three,
              backgroundColor: selected ? theme.text : theme.backgroundElement,
            }}>
            <ThemedText
              type="small"
              style={{ color: selected ? theme.background : theme.text }}>
              {option}
            </ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}
