import { Image } from "expo-image";
import { useEffect, useState } from "react";

import { API_URL } from "@/utils/api";

export function PhotoThumb({ id, token }: { id: string; token: string }) {
  const [uri, setUri] = useState<string | null>(process.env.EXPO_OS === "web" ? null : `${API_URL}/media/${id}/file`);

  useEffect(() => {
    if (process.env.EXPO_OS !== "web") return;
    let alive = true;
    let objectUrl = "";
    fetch(`${API_URL}/media/${id}/file`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => {
        if (!alive || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setUri(objectUrl);
      })
      .catch(() => {
        if (alive) setUri(null);
      });
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, token]);

  if (!uri) return null;
  return (
    <Image
      source={
        process.env.EXPO_OS === "web"
          ? { uri }
          : { uri, headers: { Authorization: `Bearer ${token}` } }
      }
      style={{ width: 96, height: 128, borderRadius: 8 }}
      contentFit="cover"
    />
  );
}
