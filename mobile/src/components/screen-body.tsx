import { ScrollView, type ScrollViewProps } from 'react-native';

import { Spacing } from '@/constants/theme';

export function ScreenBody({ children, contentContainerStyle, ...props }: ScrollViewProps) {
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentInsetAdjustmentBehavior="automatic"
      automaticallyAdjustKeyboardInsets
      contentContainerStyle={[
        {
          paddingHorizontal: Spacing.three,
          paddingTop: Spacing.two,
          paddingBottom: Spacing.six,
          gap: Spacing.four,
        },
        contentContainerStyle,
      ]}
      {...props}>
      {children}
    </ScrollView>
  );
}
