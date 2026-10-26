export type LiftPoint = {
  exercise: string;
  date: string;
  label: string;
  top_weight_lb: number;
  epley: number;
};

export type Trends = {
  lifts: LiftPoint[];
  bodyweight: { date: string; bodyweight_lb: number; mean_7d: number }[];
  nutrition: { date: string; calories: number | null; protein_g: number | null }[];
  adherence: { supplement_dates: number; day_dates: number; ratio: number | null };
  muscles: { muscle: string; week: string; volume: number }[];
};

export function latestByDate<T extends { date: string }>(rows: T[]): T | null {
  if (rows.length === 0) return null;
  return rows.slice().sort((a, b) => (a.date < b.date ? 1 : -1))[0];
}

export function latestLift(lifts: LiftPoint[]): LiftPoint | null {
  if (lifts.length === 0) return null;
  return lifts.slice().sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    return b.top_weight_lb - a.top_weight_lb;
  })[0];
}
