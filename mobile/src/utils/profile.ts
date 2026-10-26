export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export type Profile = {
  email: string;
  name?: string;
  height_in: number | null;
  split: Record<string, string>;
};

const BY_INDEX = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

const DEFAULT_SPLIT: Record<string, string> = {
  Mon: "Push",
  Tue: "Pull",
  Wed: "Legs",
  Thu: "Push",
  Fri: "Pull",
  Sat: "Legs",
  Sun: "",
};

export function weekdayKey(date = new Date()): (typeof WEEKDAYS)[number] {
  return BY_INDEX[date.getDay()];
}

export function trainingLabel(split: Record<string, string> | undefined, date = new Date()): string {
  const source = split ?? DEFAULT_SPLIT;
  const raw = source[weekdayKey(date)] ?? "";
  return raw === "" || raw === "Rest" ? "" : raw;
}

export function trainingName(split: Record<string, string> | undefined, date = new Date()): string {
  return trainingLabel(split, date) || "Rest";
}

export function shownSplit(split: Record<string, string> | undefined): Record<string, string> {
  const next: Record<string, string> = {};
  const source = split ?? DEFAULT_SPLIT;
  for (const day of WEEKDAYS) {
    const value = source[day] ?? "";
    next[day] = value === "" ? "Rest" : value;
  }
  return next;
}

export function storedSplit(split: Record<string, string>): Record<string, string> {
  const next: Record<string, string> = {};
  for (const day of WEEKDAYS) {
    next[day] = split[day] === "Rest" || !split[day] ? "" : split[day];
  }
  return next;
}
