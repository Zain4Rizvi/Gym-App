const TOKEN = "gym-token";

export async function readToken(): Promise<string | null> {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN);
}

export async function writeToken(token: string | null): Promise<void> {
  if (typeof localStorage === "undefined") return;
  if (token) localStorage.setItem(TOKEN, token);
  else localStorage.removeItem(TOKEN);
}
