import { Redirect } from "expo-router";

import { useAuth } from "@/utils/auth";

export default function Index() {
  const { token } = useAuth();
  if (!token) return <Redirect href="/login" />;
  return <Redirect href="/notes" />;
}
