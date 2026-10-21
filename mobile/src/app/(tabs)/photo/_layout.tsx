import { Stack } from "expo-router/stack";

export default function PhotoLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: "Photo" }} />
    </Stack>
  );
}
