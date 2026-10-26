import type { ReactNode } from 'react';
import { View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Radius, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Group({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View
      style={{
        backgroundColor: theme.backgroundElement,
        borderRadius: Radius.lg,
        borderCurve: 'continuous',
        overflow: 'hidden',
      }}>
      {children}
    </View>
  );
}

export function Section({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <View style={{ gap: Spacing.two }}>
      {title ? (
        <ThemedText type="headline" style={{ paddingHorizontal: Spacing.one }}>
          {title}
        </ThemedText>
      ) : null}
      {children}
    </View>
  );
}
