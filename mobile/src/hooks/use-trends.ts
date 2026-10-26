import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";

import { api } from "@/utils/api";
import { useAuth } from "@/utils/auth";
import type { Trends } from "@/utils/trends";

export function useTrends() {
  const { token } = useAuth();
  const [trends, setTrends] = useState<Trends | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!token) return;
    api<Trends>("/trends", token)
      .then((body) => {
        setTrends(body);
        setError("");
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load trends");
      });
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return { trends, error, load };
}
