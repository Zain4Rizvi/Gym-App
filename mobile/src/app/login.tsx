import { Redirect } from "expo-router";

import { LoginScreen } from "@/screens/login";
import { useAuth } from "@/utils/auth";

export default function LoginRoute() {
  const { token } = useAuth();
  if (token) return <Redirect href="/notes" />;
  return <LoginScreen />;
}
