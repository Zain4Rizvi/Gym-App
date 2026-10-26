import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { View } from "react-native";

import { Button } from "@/components/button";
import { ChoiceRow } from "@/components/choice-row";
import { Field } from "@/components/field";
import { ScreenBody } from "@/components/screen-body";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { DEMO_EMAIL } from "@/utils/demo";
import { writeDraft } from "@/utils/draft";
import { numberOrNull } from "@/utils/date";
import { shownSplit, storedSplit, WEEKDAYS, type Profile } from "@/utils/profile";

const SPLIT_OPTIONS = ["Push", "Pull", "Legs", "Rest"];

export function ProfileScreen() {
  const { token, setToken } = useAuth();
  const theme = useTheme();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [height, setHeight] = useState("");
  const [split, setSplit] = useState<Record<string, string>>(() => shownSplit(undefined));
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setError("");
    api<Profile>("/me", token)
      .then((profile) => {
        setEmail(profile.email);
        setName(profile.name || "");
        setHeight(profile.height_in == null ? "" : String(profile.height_in));
        setSplit(shownSplit(profile.split));
        setReady(true);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load account");
        setReady(true);
      });
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function save() {
    if (!token || busy) return;
    if (height.trim() !== "" && numberOrNull(height) === null) {
      setError("Height must be a number");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const profile = await api<Profile>("/me", token, {
        method: "PATCH",
        body: JSON.stringify({ height_in: numberOrNull(height), split: storedSplit(split) }),
      });
      setHeight(profile.height_in == null ? "" : String(profile.height_in));
      setSplit(shownSplit(profile.split));
      setNotice("Saved");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (!token || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/demo/reset", token, { method: "POST" });
      writeDraft(null);
      setNotice("Book reset");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reset");
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four }}>
        <ThemedText themeColor="textSecondary">Opening the record…</ThemedText>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScreenBody contentContainerStyle={{ paddingTop: Spacing.three }}>
        <View style={{ gap: 4 }}>
          <ThemedText type="title">{name || "Account"}</ThemedText>
          <ThemedText themeColor="textSecondary">{email}</ThemedText>
        </View>
        <Field label="Height (in)" keyboardType="decimal-pad" value={height} onChangeText={setHeight} />
        <View style={{ gap: Spacing.three }}>
          {WEEKDAYS.map((day) => (
            <View key={day} style={{ gap: Spacing.two }}>
              <ThemedText type="small" themeColor="textSecondary">
                {day}
              </ThemedText>
              <ChoiceRow
                options={SPLIT_OPTIONS}
                value={split[day] ?? "Rest"}
                onChange={(value) => setSplit((current) => ({ ...current, [day]: value }))}
              />
            </View>
          ))}
        </View>
        {error ? (
          <ThemedText selectable style={{ color: theme.danger }}>
            {error}
          </ThemedText>
        ) : null}
        {notice ? <ThemedText themeColor="textSecondary">{notice}</ThemedText> : null}
        <Button title={busy ? "Saving…" : "Save"} disabled={busy || !email} onPress={save} />
        {email === DEMO_EMAIL ? <Button variant="secondary" title="Reset demo" disabled={busy} onPress={reset} /> : null}
        <Button variant="secondary" title="Log out" onPress={() => setToken(null)} />
      </ScreenBody>
    </ThemedView>
  );
}
