import { Link, useFocusEffect, type Href } from "expo-router";
import { useCallback, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";

type Trends = {
  lifts: { exercise: string; date: string; top_weight_lb: number; epley: number }[];
  bodyweight: { date: string; bodyweight_lb: number; mean_7d: number }[];
  nutrition: { date: string; calories: number | null; protein_g: number | null }[];
  adherence: { supplement_dates: number; day_dates: number; ratio: number | null };
  muscles: { muscle: string; week: string; volume: number }[];
};

export function DashboardScreen() {
  const { token, setToken } = useAuth();
  const theme = useTheme();
  const [trends, setTrends] = useState<Trends | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!token) return;
    api<Trends>("/trends", token)
      .then((body) => {
        setTrends(body);
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load trends");
      });
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  if (error && !trends) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four, gap: Spacing.three }}>
        <ThemedText selectable>{error}</ThemedText>
        <Pressable accessibilityRole="button" onPress={load}>
          <ThemedText type="link">Retry</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  if (!trends) {
    return (
      <ThemedView style={{ flex: 1, padding: Spacing.four }}>
        <ThemedText>Loading dashboard…</ThemedText>
      </ThemedView>
    );
  }

  const empty =
    trends.lifts.length === 0 &&
    trends.bodyweight.length === 0 &&
    trends.nutrition.length === 0 &&
    trends.muscles.length === 0 &&
    trends.adherence.day_dates === 0;

  const maxEpley = Math.max(0, ...trends.lifts.map((row) => row.epley));

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.three, gap: Spacing.four }}>
        {empty ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText>Nothing to chart yet.</ThemedText>
            <Link href={"/notes/new" as Href} asChild>
              <Pressable accessibilityRole="button">
                <ThemedText type="link">Write a note</ThemedText>
              </Pressable>
            </Link>
          </View>
        ) : null}
        {trends.lifts.length > 0 ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText type="smallBold">Lifts</ThemedText>
            {trends.lifts.map((row) => (
              <View key={`${row.exercise}-${row.date}`} style={{ gap: Spacing.one }}>
                <ThemedText selectable>
                  {row.exercise} {row.date} · {row.top_weight_lb} lb · epley {row.epley}
                </ThemedText>
                <View style={{ height: 8, backgroundColor: theme.backgroundElement, borderRadius: 4 }}>
                  <View
                    style={{
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: theme.text,
                      width: `${maxEpley > 0 ? Math.max(4, (row.epley / maxEpley) * 100) : 0}%`,
                    }}
                  />
                </View>
              </View>
            ))}
          </View>
        ) : null}
        {trends.bodyweight.length > 0 ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText type="smallBold">Bodyweight</ThemedText>
            {trends.bodyweight.map((row) => (
              <ThemedText key={row.date} selectable>
                {row.date}: {row.bodyweight_lb} lb, 7-day mean {row.mean_7d}
              </ThemedText>
            ))}
          </View>
        ) : null}
        {trends.nutrition.length > 0 ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText type="smallBold">Nutrition</ThemedText>
            {trends.nutrition.map((row) => (
              <ThemedText key={row.date} selectable>
                {row.date}: {row.calories ?? "—"} cal, {row.protein_g ?? "—"} g protein
              </ThemedText>
            ))}
          </View>
        ) : null}
        {trends.adherence.day_dates > 0 ? (
          <ThemedText selectable>
            Supplements {trends.adherence.supplement_dates} / {trends.adherence.day_dates} days
          </ThemedText>
        ) : null}
        {trends.muscles.length > 0 ? (
          <View style={{ gap: Spacing.two }}>
            <ThemedText type="smallBold">Weekly muscle volume</ThemedText>
            {trends.muscles.map((row) => (
              <ThemedText key={`${row.muscle}-${row.week}`} selectable>
                {row.week} {row.muscle}: {row.volume}
              </ThemedText>
            ))}
          </View>
        ) : null}
        <Pressable accessibilityRole="button" onPress={() => setToken(null)}>
          <ThemedText type="small">Log out</ThemedText>
        </Pressable>
      </ScrollView>
    </ThemedView>
  );
}
