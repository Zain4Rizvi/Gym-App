import { useCallback, useState } from "react";
import { Pressable, ScrollView, TextInput, View } from "react-native";
import { useFocusEffect } from "expo-router";

import { ChoiceRow } from "@/components/choice-row";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { ApiError, api } from "@/utils/api";
import { useAuth } from "@/utils/auth";

const SET_TYPES = ["", "warmup", "working", "drop", "failure"];

type Note = {
  id: string;
  raw_text: string;
  parse_status: string;
  error_text: string;
  day_label: string;
  session_date: string;
};

type SetRow = {
  id: string;
  note_id: string;
  exercise_id: string;
  name_as_written: string;
  set_number: string;
  weight_lb: string;
  reps: string;
  rpe: string;
  set_type: string;
};

type Exercise = { id: string; canonical_name: string };

type SetDraft = {
  weight_lb: string;
  reps: string;
  rpe: string;
  set_type: string;
  exercise_id: string;
};

export function NoteDetailScreen({ id }: { id: string }) {
  const { token } = useAuth();
  const theme = useTheme();
  const [note, setNote] = useState<Note | null>(null);
  const [sets, setSets] = useState<SetDraft[]>([]);
  const [setIds, setSetIds] = useState<string[]>([]);
  const [names, setNames] = useState<string[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState(false);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    Promise.all([
      api<Note>(`/notes/${id}`, token),
      api<SetRow[]>("/sets", token),
      api<Exercise[]>("/exercises", token),
    ])
      .then(([loaded, allSets, catalog]) => {
        const mine = allSets.filter((row) => row.note_id === id);
        setNote(loaded);
        setSetIds(mine.map((row) => row.id));
        setNames(mine.map((row) => row.name_as_written));
        setSets(
          mine.map((row) => ({
            weight_lb: row.weight_lb,
            reps: row.reps,
            rpe: row.rpe,
            set_type: row.set_type,
            exercise_id: row.exercise_id,
          })),
        );
        setExercises(catalog);
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load the note");
      })
      .finally(() => setLoading(false));
  }, [id, token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function parse() {
    if (!token) return;
    setParsing(true);
    setMessage("");
    try {
      await api(`/notes/${id}/parse`, token, { method: "POST" });
      setMessage("");
      load();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        setMessage("parser not configured");
      } else {
        setMessage(caught instanceof Error ? caught.message : "Parse failed");
      }
    } finally {
      setParsing(false);
    }
  }

  function edit(index: number, partial: Partial<SetDraft>) {
    setSets((current) => current.map((row, item) => (item === index ? { ...row, ...partial } : row)));
  }

  async function saveSet(index: number) {
    if (!token) return;
    const row = sets[index];
    setMessage("");
    try {
      await api(`/sets/${setIds[index]}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          weight_lb: row.weight_lb === "" ? null : Number(row.weight_lb),
          reps: row.reps === "" ? null : Number(row.reps),
          rpe: row.rpe === "" ? null : Number(row.rpe),
          set_type: row.set_type,
          ...(row.exercise_id ? { exercise_id: row.exercise_id } : {}),
        }),
      });
      setMessage("Set saved");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not save the set");
    }
  }

  if (loading && !note) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four }}>
        <ThemedText>Loading note…</ThemedText>
      </ThemedView>
    );
  }

  if (error && !note) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four, gap: Spacing.three }}>
        <ThemedText selectable>{error}</ThemedText>
        <Pressable accessibilityRole="button" onPress={load}>
          <ThemedText type="link">Retry</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  if (!note) return null;

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.three, gap: Spacing.three }}>
        <ThemedText selectable>
          {note.session_date} {note.day_label}
        </ThemedText>
        <ThemedText selectable>{note.parse_status}</ThemedText>
        {note.error_text ? <ThemedText selectable>{note.error_text}</ThemedText> : null}
        <ThemedText selectable>{note.raw_text}</ThemedText>
        <Pressable accessibilityRole="button" disabled={parsing} onPress={parse}>
          <ThemedText type="link">{parsing ? "Parsing…" : "Parse"}</ThemedText>
        </Pressable>
        {message ? <ThemedText selectable>{message}</ThemedText> : null}
        {sets.map((row, index) => (
          <View key={setIds[index]} style={{ gap: Spacing.two }}>
            <ThemedText>
              Set {index + 1}
              {names[index] ? `: ${names[index]}` : ""}
            </ThemedText>
            <TextInput
              accessibilityLabel={`Weight ${index + 1}`}
              value={row.weight_lb}
              onChangeText={(weight_lb) => edit(index, { weight_lb })}
              keyboardType="decimal-pad"
              placeholder="Weight"
              placeholderTextColor={theme.textSecondary}
              style={inputStyle(theme.text, theme.backgroundElement)}
            />
            <TextInput
              accessibilityLabel={`Reps ${index + 1}`}
              value={row.reps}
              onChangeText={(reps) => edit(index, { reps })}
              keyboardType="number-pad"
              placeholder="Reps"
              placeholderTextColor={theme.textSecondary}
              style={inputStyle(theme.text, theme.backgroundElement)}
            />
            <TextInput
              accessibilityLabel={`RPE ${index + 1}`}
              value={row.rpe}
              onChangeText={(rpe) => edit(index, { rpe })}
              keyboardType="decimal-pad"
              placeholder="RPE"
              placeholderTextColor={theme.textSecondary}
              style={inputStyle(theme.text, theme.backgroundElement)}
            />
            <ChoiceRow
              options={SET_TYPES.map((item) => (item === "" ? "unset" : item))}
              value={row.set_type === "" ? "unset" : row.set_type}
              onChange={(value) => edit(index, { set_type: value === "unset" ? "" : value })}
            />
            <ThemedText type="small">Exercise</ThemedText>
            <ChoiceRow
              options={exercises.map((item) => item.canonical_name)}
              value={exercises.find((item) => item.id === row.exercise_id)?.canonical_name ?? ""}
              onChange={(name) => {
                const found = exercises.find((item) => item.canonical_name === name);
                if (found) edit(index, { exercise_id: found.id });
              }}
            />
            <Pressable accessibilityRole="button" onPress={() => saveSet(index)}>
              <ThemedText type="link">Save set</ThemedText>
            </Pressable>
          </View>
        ))}
      </ScrollView>
    </ThemedView>
  );
}

function inputStyle(color: string, backgroundColor: string) {
  return {
    color,
    backgroundColor,
    borderRadius: Spacing.two,
    padding: Spacing.three,
  };
}
