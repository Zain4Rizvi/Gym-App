import { createContext, use, useEffect, useState, type ReactNode } from "react";

import { readToken, writeToken } from "@/utils/session";

type AuthValue = {
  token: string | null;
  ready: boolean;
  setToken: (token: string | null) => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    readToken()
      .then((value) => {
        if (alive) setTokenState(value);
      })
      .finally(() => {
        if (alive) setReady(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function setToken(value: string | null) {
    await writeToken(value);
    setTokenState(value);
  }

  return <AuthContext.Provider value={{ token, ready, setToken }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = use(AuthContext);
  if (!value) throw new Error("AuthProvider missing");
  return value;
}
