import { Redirect } from "expo-router";

import { AccountScreen } from "@/screens/account";
import { useAuth } from "@/utils/auth";

export default function LoginRoute() {
  const { token } = useAuth();
  if (token) return <Redirect href="/notes" />;
  return <AccountScreen />;
}
