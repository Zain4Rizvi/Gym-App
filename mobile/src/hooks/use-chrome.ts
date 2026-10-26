import { useTheme } from '@/hooks/use-theme';

export function useChrome() {
  const theme = useTheme();
  return {
    headerShadowVisible: false,
    headerStyle: { backgroundColor: theme.background },
    headerTintColor: theme.accent,
    headerTitleStyle: { fontWeight: '600' as const, color: theme.text },
    contentStyle: { backgroundColor: theme.background },
  };
}
