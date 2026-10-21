import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { ChoiceRow } from "@/components/choice-row";
import { Field } from "@/components/field";
import type { PickedPhoto } from "@/components/picked-photo";
import { PhotoPicker } from "@/components/photo-picker";
import { PhotoThumb } from "@/components/photo-thumb";
import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";
import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import { DATE_RE, today } from "@/utils/date";

const POSES = ["front", "side", "back"];

type MediaRow = { id: string; pose: string; date: string };

export function PhotoScreen() {
  const { token } = useAuth();
  const [date, setDate] = useState(today());
  const [pose, setPose] = useState("");
  const [photo, setPhoto] = useState<PickedPhoto | null>(null);
  const [rows, setRows] = useState<MediaRow[] | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(() => {
    if (!token || !DATE_RE.test(date)) return;
    api<MediaRow[]>(`/media?date=${date}`, token)
      .then((loaded) => {
        setRows(loaded);
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load photos");
      });
  }, [date, token]);

  useEffect(() => {
    load();
  }, [load]);

  async function upload() {
    if (!token || !photo || pose === "" || uploading) return;
    if (!DATE_RE.test(date)) {
      setError("Date must be YYYY-MM-DD");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("date", date);
      body.append("pose", pose);
      if (photo.file) body.append("file", photo.file);
      else {
        body.append("file", { uri: photo.uri, name: photo.name, type: photo.type } as unknown as Blob);
      }
      await api("/media", token, { method: "POST", body });
      setPhoto(null);
      load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const canUpload = photo !== null && pose !== "" && !uploading;

  return (
    <ThemedView style={{ flex: 1 }}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: Spacing.three, gap: Spacing.three }}>
        <Field label="Date" value={date} onChangeText={setDate} />
        <ThemedText type="small">Pose</ThemedText>
        <ChoiceRow options={POSES} value={pose} onChange={setPose} />
        <PhotoPicker onPick={setPhoto} />
        {photo ? <ThemedText selectable>{photo.name}</ThemedText> : null}
        <Pressable accessibilityRole="button" accessibilityState={{ disabled: !canUpload }} disabled={!canUpload} onPress={upload}>
          <ThemedText type="link" style={{ opacity: canUpload ? 1 : 0.4 }}>
            {uploading ? "Uploading…" : "Upload"}
          </ThemedText>
        </Pressable>
        {error ? <ThemedText selectable>{error}</ThemedText> : null}
        {rows === null ? <ThemedText>Loading photos…</ThemedText> : null}
        {rows?.length === 0 ? <ThemedText>No photos for this date.</ThemedText> : null}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: Spacing.three }}>
          {token
            ? rows?.map((row) => (
                <View key={row.id} style={{ gap: Spacing.one }}>
                  <PhotoThumb id={row.id} token={token} />
                  <ThemedText type="small">{row.pose}</ThemedText>
                </View>
              ))
            : null}
        </View>
      </ScrollView>
    </ThemedView>
  );
}
