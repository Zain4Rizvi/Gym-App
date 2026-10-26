import { DarkTheme, ThemeProvider } from "expo-router";
import { Stack } from "expo-router/stack";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";

import { PhoneFrame } from "@/components/phone-frame";
import { useTheme } from "@/hooks/use-theme";
import { AuthProvider, useAuth } from "@/utils/auth";

SplashScreen.preventAutoHideAsync();

function RootStack() {
  const theme = useTheme();
  const { ready } = useAuth();

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;

  return (
    <ThemeProvider
      value={{
        ...DarkTheme,
        colors: {
          ...DarkTheme.colors,
          primary: theme.accent,
          background: theme.background,
          card: theme.background,
          text: theme.text,
          border: theme.separator,
          notification: theme.accent,
        },
      }}>
      <StatusBar style="light" />
      <PhoneFrame>
        <Stack
          screenOptions={{
            headerShadowVisible: false,
            headerStyle: { backgroundColor: theme.background },
            headerTintColor: theme.accent,
            headerTitleStyle: { fontWeight: "600", color: theme.text },
            contentStyle: { backgroundColor: theme.background },
          }}>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="login" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        </Stack>
      </PhoneFrame>
    </ThemeProvider>
  );
}

export default function Layout() {
  return (
    <AuthProvider>
      <RootStack />
    </AuthProvider>
  );
}
