import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { Field } from "@/components/field";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { ApiError, api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { DATE_RE, numberOrNull, today } from "@/utils/date";

type DayRow = {
  bodyweight_lb: string;
  sleep_hours: string;
  steps: string;
  summary: string;
};

type NutritionRow = {
  calories: string;
  protein_g: string;
  carbs_g: string;
  fat_g: string;
};

type Item = { item: string; active: string };
type Logged = { item: string };
type Context = { id: string; text: string };

const emptyDay = { bodyweight_lb: "", sleep_hours: "", steps: "", summary: "" };
const emptyFood = { calories: "", protein_g: "", carbs_g: "", fat_g: "" };

export function DayScreen() {
  const { token } = useAuth();
  const [date, setDate] = useState(today());
  const [day, setDay] = useState(emptyDay);
  const [food, setFood] = useState(emptyFood);
  const [items, setItems] = useState<Item[]>([]);
  const [logged, setLogged] = useState<string[]>([]);
  const [contextId, setContextId] = useState("");
  const [context, setContext] = useState("");
  const [newItem, setNewItem] = useState("");
  const [dose, setDose] = useState("");
  const [unit, setUnit] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!token || !DATE_RE.test(date)) return;
    setLoading(true);
    setError("");
    try {
      const [dayResult, foodResult, checklist, taken, notes] = await Promise.all([
        api<DayRow>(`/days/${date}`, token).catch((caught: unknown) =>
          caught instanceof ApiError && caught.status === 404 ? null : Promise.reject(caught),
        ),
        api<NutritionRow>(`/nutrition/${date}`, token).catch((caught: unknown) =>
          caught instanceof ApiError && caught.status === 404 ? null : Promise.reject(caught),
        ),
        api<Item[]>("/supplement-items", token),
        api<Logged[]>(`/supplements?date=${date}`, token),
        api<Context[]>(`/context-notes?date=${date}`, token),
      ]);
      setDay(dayResult ?? emptyDay);
      setFood(foodResult ?? emptyFood);
      setItems(checklist.filter((item) => item.active !== "FALSE"));
      setLogged(taken.map((item) => item.item.toLowerCase()));
      setContextId(notes[0]?.id ?? "");
      setContext(notes[0]?.text ?? "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the day");
    } finally {
      setLoading(false);
    }
  }, [date, token]);

  useEffect(() => {
    load();
  }, [load]);

  async function save() {
    if (!token || saving) return;
    if (!DATE_RE.test(date)) {
      setError("Date must be YYYY-MM-DD");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api(`/days/${date}`, token, {
        method: "PUT",
        body: JSON.stringify({
          bodyweight_lb: numberOrNull(day.bodyweight_lb),
          sleep_hours: numberOrNull(day.sleep_hours),
          steps: numberOrNull(day.steps),
          summary: day.summary.trim() === "" ? null : day.summary,
        }),
      });
      await api(`/nutrition/${date}`, token, {
        method: "PUT",
        body: JSON.stringify({
          calories: numberOrNull(food.calories),
          protein_g: numberOrNull(food.protein_g),
          carbs_g: numberOrNull(food.carbs_g),
          fat_g: numberOrNull(food.fat_g),
        }),
      });
      if (contextId) {
        await api(`/context-notes/${contextId}`, token, {
          method: "PATCH",
          body: JSON.stringify({ text: context.trim() === "" ? null : context }),
        });
      } else if (context.trim() !== "") {
        await api("/context-notes", token, {
          method: "POST",
          body: JSON.stringify({ date, text: context }),
        });
      }
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the day");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(item: string) {
    if (!token) return;
    await api("/supplements/toggle", token, {
      method: "POST",
      body: JSON.stringify({ date, item }),
    });
    await load();
  }

  async function addItem() {
    if (!token || newItem.trim() === "") return;
    await api("/supplement-items", token, {
      method: "POST",
      body: JSON.stringify({
        item: newItem.trim(),
        default_dose: dose.trim() === "" ? null : dose.trim(),
        unit: unit.trim(),
        active: true,
      }),
    });
    setNewItem("");
    setDose("");
    setUnit("");
    await load();
  }

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.three, gap: Spacing.three }}>
        <Field label="Date" value={date} onChangeText={setDate} />
        {loading ? <ThemedText>Loading day…</ThemedText> : null}
        {error ? <ThemedText selectable>{error}</ThemedText> : null}
        <Field label="Bodyweight" value={day.bodyweight_lb} keyboardType="decimal-pad" onChangeText={(bodyweight_lb) => setDay({ ...day, bodyweight_lb })} />
        <Field label="Sleep hours" value={day.sleep_hours} keyboardType="decimal-pad" onChangeText={(sleep_hours) => setDay({ ...day, sleep_hours })} />
        <Field label="Steps" value={day.steps} keyboardType="number-pad" onChangeText={(steps) => setDay({ ...day, steps })} />
        <Field label="Summary" value={day.summary} onChangeText={(summary) => setDay({ ...day, summary })} />
        <Field label="Calories" value={food.calories} keyboardType="number-pad" onChangeText={(calories) => setFood({ ...food, calories })} />
        <Field label="Protein" value={food.protein_g} keyboardType="decimal-pad" onChangeText={(protein_g) => setFood({ ...food, protein_g })} />
        <Field label="Carbs" value={food.carbs_g} keyboardType="decimal-pad" onChangeText={(carbs_g) => setFood({ ...food, carbs_g })} />
        <Field label="Fat" value={food.fat_g} keyboardType="decimal-pad" onChangeText={(fat_g) => setFood({ ...food, fat_g })} />
        <Pressable accessibilityRole="button" disabled={saving} onPress={save}>
          <ThemedText type="link">{saving ? "Saving…" : "Save day"}</ThemedText>
        </Pressable>
        <ThemedText type="smallBold">Supplements</ThemedText>
        {items.length === 0 ? <ThemedText>No checklist items yet.</ThemedText> : null}
        {items.map((item) => {
          const on = logged.includes(item.item.toLowerCase());
          return (
            <Pressable key={item.item} accessibilityRole="button" onPress={() => toggle(item.item)}>
              <ThemedText>
                {on ? "On" : "Off"} · {item.item}
              </ThemedText>
            </Pressable>
          );
        })}
        <View style={{ gap: Spacing.two }}>
          <Field label="New supplement" value={newItem} onChangeText={setNewItem} />
          <Field label="Default dose" value={dose} onChangeText={setDose} />
          <Field label="Unit" value={unit} onChangeText={setUnit} />
          <Pressable accessibilityRole="button" onPress={addItem}>
            <ThemedText type="link">Add to checklist</ThemedText>
          </Pressable>
        </View>
        <Field label="Context note" value={context} onChangeText={setContext} multiline />
      </ScrollView>
    </ThemedView>
  );
}
