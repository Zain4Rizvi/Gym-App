import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, TextInput } from "react-native";

import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { today, uuid4 } from "@/utils/date";
import { readDraft, writeDraft } from "@/utils/draft";

type Note = {
  id: string;
  raw_text: string;
  session_date: string;
  parse_status: string;
  created_at: string;
  updated_at: string;
  client_request_id: string;
};

const PARSE_WAIT = 1200;

function newest(notes: Note[]): Note | undefined {
  return notes.reduce<Note | undefined>((best, note) => {
    if (!best) return note;
    const stamp = note.updated_at || note.created_at;
    const bestStamp = best.updated_at || best.created_at;
    return stamp > bestStamp ? note : best;
  }, undefined);
}

export function NotesScreen() {
  const { token } = useAuth();
  const theme = useTheme();
  const [opening] = useState(() => {
    const stored = readDraft();
    return stored?.session_date === today() ? stored : null;
  });
  const [text, setText] = useState(opening?.raw_text ?? "");
  const textRef = useRef(text);
  const idRef = useRef<string | null>(opening?.note_id ?? null);
  const requestRef = useRef(opening?.client_request_id || uuid4());
  const savedRef = useRef<string | null>(null);
  const parsedRef = useRef<string | null>(null);
  const typed = useRef(false);
  const loaded = useRef(false);
  const tokenRef = useRef(token);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const parseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chain = useRef(Promise.resolve());

  const persist = useCallback(async (current: string) => {
    async function save(value: string): Promise<void> {
      const auth = tokenRef.current;
      if (!auth || !loaded.current) return;
      if (value === savedRef.current && idRef.current) return;
      if (value.trim() === "" && !idRef.current) return;
      const draft = {
        client_request_id: requestRef.current,
        raw_text: value,
        session_date: today(),
        day_label: "",
        note_id: idRef.current ?? undefined,
      };
      try {
        if (!idRef.current) {
          const created = await api<{ note: Note }>("/notes", auth, {
            method: "POST",
            body: JSON.stringify({
              client_request_id: requestRef.current,
              raw_text: value,
              session_date: today(),
              day_label: "",
              defer_parse: true,
            }),
          });
          idRef.current = created.note.id;
          draft.note_id = created.note.id;
          if (created.note.raw_text !== value) {
            await api(`/notes/${created.note.id}`, auth, {
              method: "PATCH",
              body: JSON.stringify({ raw_text: value, defer_parse: true }),
            });
          }
        } else {
          await api(`/notes/${idRef.current}`, auth, {
            method: "PATCH",
            body: JSON.stringify({ raw_text: value, defer_parse: true }),
          });
        }
        savedRef.current = value;
        writeDraft(draft);
        if (textRef.current !== value) await save(textRef.current);
      } catch {
        // The field and the draft still have the text. The next change retries.
      }
    }
    await save(current);
  }, []);

  const parseCurrent = useCallback(async (current: string) => {
    const auth = tokenRef.current;
    const id = idRef.current;
    if (!auth || !id || current.trim() === "") return;
    if (parsedRef.current === current) return;
    if (textRef.current !== current) return;
    try {
      await api(`/notes/${id}/parse`, auth, { method: "POST" });
      if (textRef.current === current) parsedRef.current = current;
    } catch {
      // Today keeps showing the unread note. The next pause tries again.
    }
  }, []);

  useLayoutEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const schedule = useCallback((current: string) => {
    if (timer.current) clearTimeout(timer.current);
    if (parseTimer.current) clearTimeout(parseTimer.current);
    timer.current = setTimeout(() => {
      chain.current = chain.current.then(() => persist(current));
    }, 400);
    parseTimer.current = setTimeout(() => {
      chain.current = chain.current.then(() => parseCurrent(current));
    }, PARSE_WAIT);
  }, [parseCurrent, persist]);

  function update(value: string) {
    typed.current = true;
    setText(value);
    textRef.current = value;
    writeDraft({
      client_request_id: requestRef.current,
      raw_text: value,
      session_date: today(),
      day_label: "",
      note_id: idRef.current ?? undefined,
    });
    schedule(value);
  }

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
      if (parseTimer.current) clearTimeout(parseTimer.current);
      const current = textRef.current;
      chain.current = chain.current.then(() => persist(current)).then(() => parseCurrent(current));
    };
  }, [parseCurrent, persist]);

  useEffect(() => {
    if (!token) return;
    let cancel = false;
    api<Note[]>("/notes", token)
      .then((rows) => {
        if (cancel) return;
        loaded.current = true;
        const note = newest(rows.filter((item) => item.session_date === today()));
        if (!note) {
          if (textRef.current.trim() !== "") schedule(textRef.current);
          return;
        }
        idRef.current = note.id;
        if (note.client_request_id) requestRef.current = note.client_request_id;
        if (note.parse_status === "done") parsedRef.current = note.raw_text;
        const local = textRef.current;
        const sameNote = opening?.note_id === note.id;
        if (typed.current || (sameNote && local !== note.raw_text)) {
          schedule(local);
          return;
        }
        textRef.current = note.raw_text;
        savedRef.current = note.raw_text;
        setText(note.raw_text);
        writeDraft({
          client_request_id: requestRef.current,
          raw_text: note.raw_text,
          session_date: today(),
          day_label: "",
          note_id: note.id,
        });
        if (note.parse_status !== "done" && note.raw_text.trim() !== "") schedule(note.raw_text);
      })
      .catch(() => {
        if (cancel) return;
        loaded.current = true;
        if (textRef.current.trim() !== "") schedule(textRef.current);
      });
    return () => {
      cancel = true;
    };
  }, [opening?.note_id, schedule, token]);

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <TextInput
        accessibilityLabel="Notes"
        autoFocus
        multiline
        value={text}
        onChangeText={update}
        selectionColor={theme.accent}
        style={{
          flex: 1,
          color: theme.text,
          fontSize: 17,
          lineHeight: 24,
          textAlignVertical: "top",
          paddingHorizontal: Spacing.four,
          paddingTop: Spacing.three,
          paddingBottom: Spacing.four,
        }}
      />
    </KeyboardAvoidingView>
  );
}
