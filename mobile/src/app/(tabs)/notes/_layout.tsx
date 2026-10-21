import { Stack } from "expo-router/stack";

export default function NotesLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: "Notes" }} />
      <Stack.Screen name="new" options={{ title: "New note" }} />
      <Stack.Screen name="[id]" options={{ title: "Note" }} />
    </Stack>
  );
}
