import { createElement } from "react";

import type { PickedPhoto } from "@/components/picked-photo";

export function PhotoPicker({ onPick }: { onPick: (photo: PickedPhoto) => void }) {
  return createElement("input", {
    type: "file",
    accept: "image/*",
    "aria-label": "Choose a photo",
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
  });
}
