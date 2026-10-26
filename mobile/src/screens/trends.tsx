import { useState } from "react";
import { Pressable, View } from "react-native";

import { Button } from "@/components/button";
import { ChoiceRow } from "@/components/choice-row";
import { DatedChart } from "@/components/dated-chart";
import { ScreenBody } from "@/components/screen-body";
import { Sparkline } from "@/components/sparkline";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing, webCursor } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { useTrends } from "@/hooks/use-trends";
import { figure, signed } from "@/utils/figures";
import { shortDate } from "@/utils/date";
import type { LiftPoint, Trends } from "@/utils/trends";

const SEGMENTS = ["Strength", "Body", "Fuel"] as const;

const POPULAR = [
  "Bench Press",
  "Barbell Squat",
  "Deadlift",
  "Shoulder Press",
  "Overhead Press",
  "Barbell Row",
  "Pull Up",
  "Chin Up",
  "Dip",
  "Incline Bench Press",
  "Incline Dumbbell Press",
  "Dumbbell Bench Press",
  "Incline Chest Press",
  "Incline Smith Press",
  "Lat Pulldown",
  "Seated Row",
  "T Bar Row",
  "Romanian Deadlift",
  "Leg Press",
  "Hack Squat",
  "Front Squat",
  "Chest Fly",
  "Lateral Raise",
  "Rear Delt Fly",
  "Bicep Curl",
  "Preacher Curl",
  "Hammer Curl",
  "Tricep Pushdown",
  "Skull Crusher",
  "Tricep Extension",
  "Tricep Press",
  "Shrug",
  "Leg Curl",
  "Leg Extension",
  "Calf Raise",
  "Back Extension",
  "Ab Crunch",
];

const RANK = new Map(POPULAR.map((name, index) => [name.toLowerCase(), index]));

function series(lifts: LiftPoint[], name: string): LiftPoint[] {
  return lifts.filter((row) => row.exercise === name);
}

function liftNames(lifts: LiftPoint[]): string[] {
  const counts = new Map<string, number>();
  for (const row of lifts) counts.set(row.exercise, (counts.get(row.exercise) ?? 0) + 1);
  return [...counts.keys()].sort((left, right) => {
    const leftRank = RANK.get(left.toLowerCase()) ?? POPULAR.length;
    const rightRank = RANK.get(right.toLowerCase()) ?? POPULAR.length;
    if (leftRank !== rightRank) return leftRank - rightRank;
    const leftCount = counts.get(left) ?? 0;
    const rightCount = counts.get(right) ?? 0;
    if (leftCount !== rightCount) return rightCount - leftCount;
    return left.localeCompare(right);
  });
}

function weightOn(days: Trends["bodyweight"], date: string): number | null {
  const exact = days.find((row) => row.date === date);
  if (exact) return exact.bodyweight_lb;
  const prior = [...days].reverse().find((row) => row.date <= date);
  return prior?.bodyweight_lb ?? null;
}

export function TrendsScreen() {
  const theme = useTheme();
  const { trends, error, load } = useTrends();
  const [segment, setSegment] = useState<(typeof SEGMENTS)[number]>("Strength");
  const [lift, setLift] = useState<string | null>(null);

  if (error && !trends) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four, gap: Spacing.three }}>
        <ThemedText selectable style={{ color: theme.danger }}>{error}</ThemedText>
        <Button variant="secondary" title="Retry" onPress={load} />
      </ThemedView>
    );
  }

  if (!trends) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four }}>
        <ThemedText themeColor="textSecondary">Opening the record…</ThemedText>
      </ThemedView>
    );
  }

  const weight = trends.bodyweight.at(-1);
  const food = [...trends.nutrition].reverse().find((row) => row.calories != null || row.protein_g != null);
  const adherence = trends.adherence;

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScreenBody contentContainerStyle={{ paddingTop: Spacing.three, gap: Spacing.five }}>
        <View style={{ gap: Spacing.two }}>
          <ThemedText type="title">Trends</ThemedText>
          <ChoiceRow
            options={SEGMENTS}
            value={segment}
            onChange={(value) => {
              setSegment(value as (typeof SEGMENTS)[number]);
              setLift(null);
            }}
          />
        </View>

        {segment === "Strength" ? <Strength lifts={trends.lifts} bodyweight={trends.bodyweight} lift={lift} onOpen={setLift} /> : null}

        {segment === "Body" && weight ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText type="small" themeColor="textSecondary" style={{ letterSpacing: 1.2, textTransform: "uppercase" }}>
              Bodyweight
            </ThemedText>
            <ThemedText selectable style={{ fontSize: 56, lineHeight: 60, fontWeight: "600", letterSpacing: -2, fontVariant: ["tabular-nums"] }}>
              {figure(weight.bodyweight_lb)}
            </ThemedText>
            <ThemedText themeColor="textSecondary">7-day mean {figure(weight.mean_7d)} lb</ThemedText>
            <Sparkline
              values={trends.bodyweight.map((row) => row.bodyweight_lb)}
              comparison={trends.bodyweight.map((row) => row.mean_7d)}
            />
          </View>
        ) : null}

        {segment === "Fuel" ? (
          <View style={{ gap: Spacing.four }}>
            <View style={{ gap: Spacing.two }}>
              <ThemedText type="small" themeColor="textSecondary" style={{ letterSpacing: 1.2, textTransform: "uppercase" }}>
                Calories
              </ThemedText>
              <ThemedText selectable style={{ fontSize: 56, lineHeight: 60, fontWeight: "600", letterSpacing: -2, fontVariant: ["tabular-nums"] }}>
                {figure(food?.calories, 0)}
              </ThemedText>
              <Sparkline values={trends.nutrition.map((row) => row.calories).filter((value): value is number => value != null)} />
            </View>
            <View style={{ gap: Spacing.two }}>
              <ThemedText type="small" themeColor="textSecondary" style={{ letterSpacing: 1.2, textTransform: "uppercase" }}>
                Protein
              </ThemedText>
              <ThemedText selectable style={{ fontSize: 40, lineHeight: 44, fontWeight: "600", letterSpacing: -1, fontVariant: ["tabular-nums"] }}>
                {figure(food?.protein_g, 0)} g
              </ThemedText>
              <Sparkline values={trends.nutrition.map((row) => row.protein_g).filter((value): value is number => value != null)} />
            </View>
            <ThemedText themeColor="textSecondary">
              Supplements {adherence.supplement_dates} of {adherence.day_dates} days
            </ThemedText>
          </View>
        ) : null}
      </ScreenBody>
    </ThemedView>
  );
}

function Strength({
  lifts,
  bodyweight,
  lift,
  onOpen,
}: {
  lifts: LiftPoint[];
  bodyweight: Trends["bodyweight"];
  lift: string | null;
  onOpen: (name: string | null) => void;
}) {
  const theme = useTheme();
  const names = liftNames(lifts);
  if (lift) {
    const points = series(lifts, lift);
    const last = points.at(-1);
    const first = points[0];
    const delta = first && last ? last.epley - first.epley : null;
    const weights = points.map((point) => weightOn(bodyweight, point.date));
    const relative = points.map((point, index) => {
      const weight = weights[index];
      return weight ? point.epley / weight : null;
    });
    const firstRatio = relative.find((value) => value != null) ?? null;
    const lastRatio = [...relative].reverse().find((value) => value != null) ?? null;
    const relativeDelta = firstRatio != null && lastRatio != null ? lastRatio - firstRatio : null;
    return (
      <View style={{ gap: Spacing.three }}>
        <Pressable accessibilityRole="button" onPress={() => onOpen(null)} style={webCursor}>
          <ThemedText themeColor="textSecondary">Lifts</ThemedText>
        </Pressable>
        <View style={{ gap: Spacing.two }}>
          <ThemedText type="title">{lift}</ThemedText>
          <ThemedText selectable style={{ fontSize: 56, lineHeight: 60, fontWeight: "600", letterSpacing: -2, fontVariant: ["tabular-nums"] }}>
            {figure(last?.epley)}
          </ThemedText>
          <ThemedText themeColor="textSecondary">estimated 1RM · {figure(last?.top_weight_lb, 0)} lb top set</ThemedText>
          {delta != null && first ? (
            <ThemedText selectable style={{ color: delta >= 0 ? theme.accent : theme.danger, fontVariant: ["tabular-nums"] }}>
              {signed(delta)} since {shortDate(first.date)}
            </ThemedText>
          ) : null}
          {lastRatio != null ? (
            <ThemedText selectable style={{ fontVariant: ["tabular-nums"] }}>
              {figure(lastRatio, 2)} per lb
              {relativeDelta != null ? `  ${signed(relativeDelta, 2)}` : ""}
            </ThemedText>
          ) : null}
        </View>
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <ThemedText type="small" style={{ color: theme.accent }}>
            1RM
          </ThemedText>
          {lastRatio != null ? (
            <ThemedText type="small" style={{ color: "#7AA2FF" }}>
              per lb
            </ThemedText>
          ) : null}
        </View>
        <DatedChart
          points={points.map((point) => ({ date: point.date, value: point.epley }))}
          relative={relative}
        />
      </View>
    );
  }

  return (
    <View style={{ gap: 2 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", paddingHorizontal: Spacing.two, paddingBottom: Spacing.two }}>
        <ThemedText type="small" themeColor="textSecondary">
          Lift
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          1RM
        </ThemedText>
      </View>
      {names.map((name) => {
        const row = series(lifts, name).at(-1);
        return (
          <Pressable
            key={name}
            accessibilityRole="button"
            onPress={() => onOpen(name)}
            style={({ pressed }) => [
              {
                minHeight: 48,
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                gap: Spacing.three,
                paddingHorizontal: Spacing.two,
                borderRadius: 12,
                backgroundColor: pressed ? theme.backgroundElement : "transparent",
              },
              webCursor,
            ]}>
            <ThemedText style={{ flex: 1 }}>{name}</ThemedText>
            <ThemedText selectable style={{ fontVariant: ["tabular-nums"] }}>
              {figure(row?.epley)}
            </ThemedText>
          </Pressable>
        );
      })}
    </View>
  );
}
