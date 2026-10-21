import * as SecureStore from "expo-secure-store";

const TOKEN = "gym-token";

export async function readToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN);
}

export async function writeToken(token: string | null): Promise<void> {
  if (token) await SecureStore.setItemAsync(TOKEN, token);
  else await SecureStore.deleteItemAsync(TOKEN);
}
