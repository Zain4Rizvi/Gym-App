import { createElement } from "react";

import type { PickedPhoto } from "@/components/picked-photo";
import { useTheme } from "@/hooks/use-theme";

export function PhotoPicker({ onPick }: { onPick: (photo: PickedPhoto) => void }) {
  const theme = useTheme();
  return createElement(
    "label",
    {
      style: {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "48px",
        padding: "0 16px",
        borderRadius: "12px",
        background: String(theme.accent),
        color: String(theme.onAccent),
        font: '600 17px ui-sans-serif, system-ui, sans-serif',
        cursor: "pointer",
        position: "relative",
        width: "100%",
        boxSizing: "border-box",
      },
    },
    "Choose photo",
    createElement("input", {
      type: "file",
      accept: "image/*",
      "aria-label": "Choose a photo",
      style: {
        position: "absolute",
        inset: "0",
        opacity: 0,
        cursor: "pointer",
        width: "100%",
        height: "100%",
      },
      onChange: (event: Event) => {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0];
        if (!file) return;
        onPick({
          uri: URL.createObjectURL(file),
          name: file.name,
          type: file.type || "image/jpeg",
          file,
        });
      },
    }),
  );
}
