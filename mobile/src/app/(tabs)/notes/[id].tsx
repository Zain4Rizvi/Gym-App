import { useLocalSearchParams } from "expo-router";

import { NoteDetailScreen } from "@/screens/note-detail";

export default function NoteRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <NoteDetailScreen id={id} />;
}
