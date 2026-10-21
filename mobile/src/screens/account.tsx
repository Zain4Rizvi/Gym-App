import { useState } from "react";
import { Pressable, ScrollView } from "react-native";

import { Field } from "@/components/field";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useAuth } from "@/utils/auth";
import { ApiError, api } from "@/utils/api";

export function AccountScreen() {
  const { setToken } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(path: "/accounts" | "/login") {
    setBusy(true);
    setError("");
    try {
      const body = await api<{ token: string; email: string }>(path, null, {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      await setToken(body.token);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError("That email is already registered");
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError("Email or password is wrong");
      } else {
        setError(caught instanceof Error ? caught.message : "Request failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.four, gap: Spacing.three }}>
        <Field
          label="Email"
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <Field
          label="Password"
          secureTextEntry
          autoComplete="password"
          value={password}
          onChangeText={setPassword}
        />
        {error ? (
          <ThemedText selectable themeColor="text">
            {error}
          </ThemedText>
        ) : null}
        <Pressable
          accessibilityRole="button"
          disabled={busy || email.trim() === "" || password === ""}
          onPress={() => submit("/accounts")}>
          <ThemedText type="link">{busy ? "Working…" : "Create account"}</ThemedText>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={busy || email.trim() === "" || password === ""}
          onPress={() => submit("/login")}>
          <ThemedText type="link">{busy ? "Working…" : "Log in"}</ThemedText>
        </Pressable>
      </ScrollView>
    </ThemedView>
  );
}
