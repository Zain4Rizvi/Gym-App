import { useRef, useState, type ComponentRef } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { Button } from "@/components/button";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Radius, Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { ApiError, api } from "@/utils/api";
import { useAuth } from "@/utils/auth";

type Turn = { role: "user" | "assistant"; content: string };

// ponytail: module memory dies on refresh; store a tab if a thread should survive reload
const thread: Turn[] = [];

function remember(next: Turn[]) {
  thread.splice(0, thread.length, ...next);
}

export function CoachScreen() {
  const theme = useTheme();
  const { token } = useAuth();
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);
  const [messages, setMessages] = useState<Turn[]>(() => [...thread]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    const content = draft.trim();
    if (content === "" || sending || !token) return;
    const pending = [...messages, { role: "user" as const, content }];
    remember(pending);
    setMessages(pending);
    setDraft("");
    setSending(true);
    setError("");
    try {
      const result = await api<{ reply: string }>("/coach", token, {
        method: "POST",
        body: JSON.stringify({ messages: pending }),
      });
      const next = [...pending, { role: "assistant" as const, content: result.reply }];
      remember(next);
      setMessages(next);
    } catch (err) {
      remember(messages);
      setMessages(messages);
      setDraft(content);
      setError(err instanceof ApiError ? err.message : "Could not ask");
    } finally {
      setSending(false);
    }
  }

  return (
    <ThemedView style={{ flex: 1 }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          ref={scroller}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => scroller.current?.scrollToEnd({ animated: false })}
          contentContainerStyle={{
            paddingHorizontal: Spacing.three,
            paddingTop: Spacing.three,
            paddingBottom: Spacing.four,
            gap: Spacing.three,
            flexGrow: 1,
          }}>
          <ThemedText type="title">Coach</ThemedText>
          {messages.length === 0 ? (
            <ThemedText themeColor="textSecondary">Ask about a lift, a week, or what to do next.</ThemedText>
          ) : null}
          {messages.map((turn, index) =>
            turn.role === "user" ? (
              <View
                key={`${index}-${turn.role}`}
                style={{
                  alignSelf: "flex-end",
                  maxWidth: "88%",
                  backgroundColor: theme.backgroundElement,
                  borderRadius: Radius.lg,
                  borderCurve: "continuous",
                  paddingHorizontal: Spacing.three,
                  paddingVertical: Spacing.two,
                }}>
                <ThemedText selectable>{turn.content}</ThemedText>
              </View>
            ) : (
              <ThemedText key={`${index}-${turn.role}`} selectable>
                {turn.content.replaceAll("**", "")}
              </ThemedText>
            ),
          )}
          {sending ? <ThemedText themeColor="textSecondary">Thinking…</ThemedText> : null}
        </ScrollView>
        <View
          style={{
            borderTopWidth: StyleSheet.hairlineWidth,
            borderTopColor: theme.separator,
            paddingHorizontal: Spacing.three,
            paddingTop: Spacing.two,
            paddingBottom: Spacing.two,
            gap: Spacing.two,
          }}>
          {error ? (
            <ThemedText selectable themeColor="danger">
              {error}
            </ThemedText>
          ) : null}
          <View style={{ flexDirection: "row", alignItems: "flex-end", gap: Spacing.two }}>
            <TextInput
              accessibilityLabel="Question"
              value={draft}
              onChangeText={setDraft}
              multiline
              placeholder="Ask about your log"
              placeholderTextColor={theme.textSecondary}
              editable={!sending}
              selectionColor={theme.accent}
              style={{
                flex: 1,
                minHeight: 44,
                maxHeight: 120,
                color: theme.text,
                fontSize: 17,
                lineHeight: 22,
                backgroundColor: theme.backgroundElement,
                borderRadius: Radius.lg,
                borderCurve: "continuous",
                paddingHorizontal: Spacing.three,
                paddingVertical: Spacing.two,
              }}
            />
            <Button title="Ask" disabled={sending || draft.trim() === ""} onPress={() => void send()} />
          </View>
        </View>
      </KeyboardAvoidingView>
    </ThemedView>
  );
}
