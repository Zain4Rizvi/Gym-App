import { Redirect } from "expo-router";

import AppShell from "@/components/app-shell";
import { useAuth } from "@/utils/auth";

export default function TabsLayout() {
  const { token, ready } = useAuth();
  if (!ready) return null;
  if (!token) return <Redirect href="/login" />;
  return <AppShell />;
}
