import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ComponentRef } from "react";
import { KeyboardAvoidingView, Platform, TextInput } from "react-native";

import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { mediumDate, today, uuid4 } from "@/utils/date";
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
// ponytail: the model parser turns one note into one session, so the full log is not sent
const PARSE_LIMIT = 8000;

function ordered(notes: Note[]): Note[] {
  return [...notes].sort((left, right) => {
    const byDay = left.session_date.localeCompare(right.session_date);
    if (byDay !== 0) return byDay;
    return (left.created_at || "").localeCompare(right.created_at || "");
  });
}

function asOneNote(notes: Note[]): string {
  if (notes.length === 1) return notes[0].raw_text;
  return ordered(notes)
    .map((note) => `${mediumDate(note.session_date)}\n${note.raw_text}`.trim())
    .join("\n\n");
}

export function NotesScreen() {
  const { token } = useAuth();
  const theme = useTheme();
  const [text, setText] = useState("");
  const textRef = useRef("");
  const idRef = useRef<string | null>(null);
  const requestRef = useRef(uuid4());
  const savedRef = useRef<string | null>(null);
  const parsedRef = useRef<string | null>(null);
  const typed = useRef(false);
  const loaded = useRef(false);
  const many = useRef(false);
  const tokenRef = useRef(token);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const parseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chain = useRef(Promise.resolve());
  const dateRef = useRef(today());
  const inputRef = useRef<ComponentRef<typeof TextInput>>(null);
  const placed = useRef(false);

  const persist = useCallback(async (current: string) => {
    async function save(value: string): Promise<void> {
      const auth = tokenRef.current;
      if (!auth || !loaded.current || many.current) return;
      if (value === savedRef.current && idRef.current) return;
      if (value.trim() === "" && !idRef.current) return;
      const draft = {
        client_request_id: requestRef.current,
        raw_text: value,
        session_date: dateRef.current,
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
              session_date: dateRef.current,
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
    if (!auth || !id || many.current || current.trim() === "" || current.length > PARSE_LIMIT) return;
    if (parsedRef.current === current) return;
    if (textRef.current !== current) return;
    try {
      await api(`/notes/${id}/parse`, auth, { method: "POST" });
      if (textRef.current === current) parsedRef.current = current;
    } catch {
      // The note stays on screen. The next pause tries again.
    }
  }, []);

  useLayoutEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const schedule = useCallback((current: string) => {
    if (many.current) return;
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
      session_date: dateRef.current,
      day_label: "",
      note_id: idRef.current ?? undefined,
    });
    schedule(value);
  }

  function show(note: Note, value: string) {
    idRef.current = note.id;
    dateRef.current = note.session_date || today();
    if (note.client_request_id) requestRef.current = note.client_request_id;
    parsedRef.current = note.parse_status === "done" ? value : null;
    savedRef.current = value;
    textRef.current = value;
    setText(value);
    writeDraft({
      client_request_id: requestRef.current,
      raw_text: value,
      session_date: dateRef.current,
      day_label: "",
      note_id: note.id,
    });
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
    if (!text || placed.current) return;
    let stop = false;
    const jump = () => {
      if (stop || typeof document === "undefined") return;
      const area = document.querySelector("textarea");
      if (!(area instanceof HTMLTextAreaElement) || area.scrollHeight <= area.clientHeight + 8) return;
      area.scrollTop = area.scrollHeight;
      placed.current = true;
    };
    const timers = [0, 80, 300, 800].map((ms) => setTimeout(jump, ms));
    return () => {
      stop = true;
      timers.forEach(clearTimeout);
    };
  }, [text]);

  useEffect(() => {
    if (!token) return;
    let cancel = false;
    api<Note[]>("/notes", token)
      .then((incoming) => {
        if (cancel) return;
        loaded.current = true;
        const rows = ordered(incoming);
        if (rows.length === 0) {
          if (textRef.current.trim() !== "") schedule(textRef.current);
          return;
        }
        if (rows.length > 1) {
          many.current = true;
          const joined = asOneNote(rows);
          savedRef.current = joined;
          textRef.current = joined;
          setText(joined);
          return;
        }
        many.current = false;
        const note = rows[0];
        const stored = readDraft();
        const local = textRef.current;
        if (typed.current && local.trim() !== "" && local.length > note.raw_text.length / 2) {
          idRef.current = note.id;
          dateRef.current = note.session_date || today();
          if (note.client_request_id) requestRef.current = note.client_request_id;
          schedule(local);
          return;
        }
        if (stored?.note_id === note.id && stored.raw_text.trim() !== "" && stored.raw_text !== note.raw_text) {
          show(note, stored.raw_text);
          schedule(stored.raw_text);
          return;
        }
        show(note, note.raw_text);
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
  }, [schedule, token]);

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <TextInput
        ref={inputRef}
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
