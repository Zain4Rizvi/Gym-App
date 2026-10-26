import type { ReactNode } from "react";
import { View } from "react-native";

import { PhoneWidth } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export function PhoneFrame({ children }: { children: ReactNode }) {
  const theme = useTheme();
  if (process.env.EXPO_OS !== "web") return <>{children}</>;
  return (
    <View style={{ flex: 1, width: "100%", backgroundColor: "#050607", alignItems: "center" }}>
      <View
        style={{
          flex: 1,
          width: "100%",
          maxWidth: PhoneWidth,
          backgroundColor: theme.background,
          overflow: "hidden",
        }}>
        {children}
      </View>
    </View>
  );
}
