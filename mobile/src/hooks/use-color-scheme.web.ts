import { useColorScheme as useRNColorScheme } from 'react-native';

export function useColorScheme() {
  const scheme = useRNColorScheme();
  if (scheme === 'light' || scheme === 'dark') return scheme;
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
}
