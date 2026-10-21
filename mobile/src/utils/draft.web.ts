const KEY = "gym-note-draft";

export type Draft = {
  client_request_id: string;
  raw_text: string;
  session_date: string;
  day_label: string;
};

export function readDraft(): Draft | null {
  if (typeof localStorage === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Draft;
  } catch {
    return null;
  }
}

export function writeDraft(draft: Draft | null): void {
  if (typeof localStorage === "undefined") return;
  if (!draft) localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, JSON.stringify(draft));
}
