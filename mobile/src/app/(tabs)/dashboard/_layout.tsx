import { Stack } from "expo-router/stack";

export default function DashboardLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: "Dashboard" }} />
    </Stack>
  );
}
