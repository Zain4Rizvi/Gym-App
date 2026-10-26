import { useState } from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button } from "@/components/button";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/utils/demo";

export function LoginScreen() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { setToken } = useAuth();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function open() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const body = await api<{ token: string }>("/login", null, {
        method: "POST",
        body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
      });
      await setToken(body.token);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not open the book");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ThemedView
      style={{
        flex: 1,
        justifyContent: "space-between",
        paddingHorizontal: Spacing.four,
        paddingTop: insets.top + Spacing.six,
        paddingBottom: insets.bottom + Spacing.four,
      }}>
      <View style={{ gap: Spacing.two }}>
        <ThemedText type="title">The note is the record.</ThemedText>
        <ThemedText themeColor="textSecondary">The log is one note. Write the next day at the end.</ThemedText>
      </View>
      {error ? (
        <ThemedText selectable style={{ color: theme.danger }}>
          {error}
        </ThemedText>
      ) : null}
      <Button title={busy ? "Opening…" : "Open the book"} disabled={busy} onPress={open} />
    </ThemedView>
  );
}
