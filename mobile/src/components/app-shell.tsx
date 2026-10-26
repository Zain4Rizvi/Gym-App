import { router, Slot, usePathname } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ThemedText } from "@/components/themed-text";
import { webCursor } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

const TABS = [
  { href: "/notes", label: "Notes" },
  { href: "/trends", label: "Trends" },
  { href: "/coach", label: "Coach" },
  { href: "/account", label: "Account" },
] as const;

type Href = (typeof TABS)[number]["href"];

export default function AppShell() {
  const theme = useTheme();
  const path = usePathname();
  const insets = useSafeAreaInsets();
  const bare = TABS.some((item) => path === item.href);
  const barHeight = 52 + insets.bottom;

  function go(href: Href) {
    if (path !== href) router.replace(href);
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.background }}>
      <View style={{ flex: 1, paddingTop: bare ? insets.top : 0 }}>
        <Slot />
      </View>
      {bare ? (
        <View
          style={{
            height: barHeight,
            paddingBottom: insets.bottom,
            flexDirection: "row",
            borderTopWidth: StyleSheet.hairlineWidth,
            borderTopColor: theme.separator,
            backgroundColor: theme.background,
          }}>
          {TABS.map((item) => (
            <BarItem key={item.href} label={item.label} selected={path === item.href} onPress={() => go(item.href)} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

function BarItem({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [{ flex: 1, alignItems: "center", justifyContent: "center", gap: 6, opacity: pressed ? 0.6 : 1 }, webCursor]}>
      <View style={{ width: 16, height: 2, borderRadius: 1, backgroundColor: selected ? theme.accent : "transparent" }} />
      <ThemedText type="smallBold" style={{ color: selected ? theme.text : theme.textSecondary }}>
        {label}
      </ThemedText>
    </Pressable>
  );
}
