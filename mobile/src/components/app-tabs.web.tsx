import { Tabs, TabList, TabTrigger, TabSlot } from "expo-router/ui";
import { View } from "react-native";

import { ThemedText } from "@/components/themed-text";
import { ThemedView } from "@/components/themed-view";
import { Spacing } from "@/constants/theme";

export default function AppTabs() {
  return (
    <View style={{ flex: 1 }}>
      <Tabs>
        <TabSlot style={{ flex: 1 }} />
        <TabList asChild>
          <ThemedView
            type="backgroundElement"
            style={{ flexDirection: "row", justifyContent: "space-around", padding: Spacing.three }}>
            <TabTrigger name="notes" href="/notes">
              <ThemedText>Notes</ThemedText>
            </TabTrigger>
            <TabTrigger name="day" href="/day">
              <ThemedText>Day</ThemedText>
            </TabTrigger>
            <TabTrigger name="photo" href="/photo">
              <ThemedText>Photo</ThemedText>
            </TabTrigger>
            <TabTrigger name="dashboard" href="/dashboard">
              <ThemedText>Dashboard</ThemedText>
            </TabTrigger>
          </ThemedView>
        </TabList>
      </Tabs>
    </View>
  );
}
