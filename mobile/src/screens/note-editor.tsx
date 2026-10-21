import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, TextInput } from "react-native";

import { ChoiceRow } from "@/components/choice-row";
import { Field } from "@/components/field";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { DATE_RE, DAY_LABELS, today, uuid4 } from "@/utils/date";
import { readDraft, writeDraft, type Draft } from "@/utils/draft";

export function NoteEditorScreen() {
  const { token } = useAuth();
  const theme = useTheme();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setDraft(
      readDraft() ?? {
        client_request_id: uuid4(),
        raw_text: "",
        session_date: today(),
        day_label: "",
      },
    );
  }, []);

  function update(partial: Partial<Draft>) {
    setDraft((current) => {
      if (!current) return current;
      const next = { ...current, ...partial };
      writeDraft(next);
      return next;
    });
  }

  async function save() {
    if (!draft || !token || saving) return;
    if (!DATE_RE.test(draft.session_date)) {
      setError("Date must be YYYY-MM-DD");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api("/notes", token, {
        method: "POST",
        body: JSON.stringify({
          client_request_id: draft.client_request_id,
          raw_text: draft.raw_text,
          session_date: draft.session_date,
          day_label: draft.day_label,
        }),
      });
      writeDraft(null);
      router.replace("/notes");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!draft) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four }}>
        <ThemedText>Loading draft…</ThemedText>
      </ThemedView>
    );
  }

  const canSave = draft.day_label !== "" && !saving;

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.three, gap: Spacing.three }}>
        <Field label="Date" value={draft.session_date} onChangeText={(session_date) => update({ session_date })} />
        <ThemedText type="small">Day</ThemedText>
        <ChoiceRow
          options={DAY_LABELS}
          value={draft.day_label}
          onChange={(day_label) => update({ day_label })}
        />
        <TextInput
          accessibilityLabel="Note"
          multiline
          value={draft.raw_text}
          onChangeText={(raw_text) => update({ raw_text })}
          placeholder="Type the workout"
          placeholderTextColor={theme.textSecondary}
          style={{
            minHeight: 240,
            color: theme.text,
            fontSize: 18,
            lineHeight: 26,
            textAlignVertical: "top",
          }}
        />
        {error ? <ThemedText selectable>{error}</ThemedText> : null}
        <Pressable accessibilityRole="button" accessibilityState={{ disabled: !canSave }} disabled={!canSave} onPress={save}>
          <ThemedText type="link" style={{ opacity: canSave ? 1 : 0.4 }}>
            {saving ? "Saving…" : "Save"}
          </ThemedText>
        </Pressable>
      </ScrollView>
    </ThemedView>
  );
}
