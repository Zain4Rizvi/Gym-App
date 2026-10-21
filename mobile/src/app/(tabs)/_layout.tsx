import { Redirect } from "expo-router";

import AppTabs from "@/components/app-tabs";
import { useAuth } from "@/utils/auth";

export default function TabsLayout() {
  const { token, ready } = useAuth();
  if (!ready) return null;
  if (!token) return <Redirect href="/login" />;
  return <AppTabs />;
}
