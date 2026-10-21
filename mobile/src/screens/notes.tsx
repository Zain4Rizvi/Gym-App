import { Link, useFocusEffect, type Href } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, TextInput, View } from "react-native";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";

type Note = {
  id: string;
  raw_text: string;
  parse_status: string;
  created_at: string;
  day_label: string;
  session_date: string;
};

function titleOf(text: string): string {
  const line = text.split("\n").find((item) => item.trim() !== "");
  return line?.trim() || "Empty note";
}

export function NotesScreen() {
  const { token } = useAuth();
  const theme = useTheme();
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    if (!token) return;
    api<Note[]>("/notes", token)
      .then((rows) => {
        setNotes(rows.slice().sort((a, b) => (a.created_at < b.created_at ? 1 : -1)));
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load notes");
      });
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function remove(id: string) {
    if (!token) return;
    await api(`/notes/${id}`, token, { method: "DELETE" });
    load();
  }

  const query = search.trim().toLowerCase();
  const visible = (notes ?? []).filter((note) => {
    if (!query) return true;
    return (
      note.raw_text.toLowerCase().includes(query) ||
      note.day_label.toLowerCase().includes(query) ||
      note.session_date.includes(query)
    );
  });

  if (error && notes === null) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four, gap: Spacing.three }}>
        <ThemedText selectable>{error}</ThemedText>
        <Pressable accessibilityRole="button" onPress={load}>
          <ThemedText type="link">Retry</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  return (
    <FlatList
      style={{ flex: 1 }}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
      data={notes === null ? [] : visible}
      keyExtractor={(item) => item.id}
      ListHeaderComponent={
        <View style={{ padding: Spacing.three, gap: Spacing.two }}>
          <TextInput
            accessibilityLabel="Search notes"
            placeholder="Search"
            placeholderTextColor={theme.textSecondary}
            value={search}
            onChangeText={setSearch}
            style={{
              color: theme.text,
              backgroundColor: theme.backgroundElement,
              borderRadius: Spacing.two,
              padding: Spacing.three,
            }}
          />
          <Link href={"/notes/new" as Href} asChild>
            <Pressable accessibilityRole="button">
              <ThemedText type="link">New</ThemedText>
            </Pressable>
          </Link>
          {error ? <ThemedText selectable>{error}</ThemedText> : null}
        </View>
      }
      ListEmptyComponent={
        notes === null ? (
          <ThemedText style={{ padding: Spacing.four }}>Loading notes…</ThemedText>
        ) : (
          <ThemedText style={{ padding: Spacing.four }}>
            {query ? "No notes match that search." : "No notes yet. Write the first one."}
          </ThemedText>
        )
      }
      renderItem={({ item }) => (
        <View
          style={{
            paddingHorizontal: Spacing.three,
            paddingVertical: Spacing.three,
            flexDirection: "row",
            gap: Spacing.three,
            alignItems: "center",
          }}>
          <Link href={`/notes/${item.id}` as Href} asChild>
            <Pressable style={{ flex: 1 }} accessibilityRole="button">
              <ThemedText selectable>{titleOf(item.raw_text)}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary" selectable>
                {item.session_date} {item.day_label} · {item.parse_status}
              </ThemedText>
            </Pressable>
          </Link>
          <Pressable accessibilityRole="button" onPress={() => remove(item.id)}>
            <ThemedText type="small">Delete</ThemedText>
          </Pressable>
        </View>
      )}
    />
  );
}
