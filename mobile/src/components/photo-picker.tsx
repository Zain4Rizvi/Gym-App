import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { Pressable, View } from "react-native";

import type { PickedPhoto } from "@/components/picked-photo";
import { ThemedText } from "@/components/themed-text";
import { Spacing } from "@/constants/theme";

export function PhotoPicker({ onPick }: { onPick: (photo: PickedPhoto) => void }) {
  const [cameraNeeded, setCameraNeeded] = useState(false);

  async function launch(camera: boolean) {
    const result = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: "images", quality: 0.8 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: "images", quality: 0.8 });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    onPick({
      uri: asset.uri,
      name: asset.fileName ?? "photo.jpg",
      type: asset.mimeType ?? "image/jpeg",
    });
  }

  async function take() {
    const current = await ImagePicker.getCameraPermissionsAsync();
    if (!current.granted) {
      setCameraNeeded(true);
      return;
    }
    await launch(true);
  }

  async function grant() {
    const result = await ImagePicker.requestCameraPermissionsAsync();
    if (!result.granted) return;
    setCameraNeeded(false);
    await launch(true);
  }

  return (
    <View style={{ gap: Spacing.two }}>
      {cameraNeeded ? (
        <View style={{ gap: Spacing.two }}>
          <ThemedText selectable>Camera access is required to take a physique photo.</ThemedText>
          <Pressable accessibilityRole="button" onPress={grant}>
            <ThemedText type="link">Grant</ThemedText>
          </Pressable>
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={take}>
          <ThemedText type="link">Take photo</ThemedText>
        </Pressable>
      )}
      <Pressable accessibilityRole="button" onPress={() => launch(false)}>
        <ThemedText type="link">Choose photo</ThemedText>
      </Pressable>
    </View>
  );
}
