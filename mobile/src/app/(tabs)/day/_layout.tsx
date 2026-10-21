import { Stack } from "expo-router/stack";

export default function DayLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: "Day" }} />
    </Stack>
  );
}
