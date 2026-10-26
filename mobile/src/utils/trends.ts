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
};
