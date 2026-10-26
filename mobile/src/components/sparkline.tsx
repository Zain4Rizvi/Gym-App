import { View } from "react-native";
import Svg, { Polyline } from "react-native-svg";

import { useTheme } from "@/hooks/use-theme";

export function Sparkline({
  values,
  comparison,
  height = 72,
}: {
  values: number[];
  comparison?: number[];
  height?: number;
}) {
  const theme = useTheme();
  const width = 320;
  const series = [values, comparison ?? []].filter((row) => row.length > 1);
  const flat = series.flat();
  if (values.length < 2 || flat.length < 2) {
    return <View style={{ height }} />;
  }
  const min = Math.min(...flat);
  const max = Math.max(...flat);
  const span = max - min || 1;

  function points(row: number[]): string {
    return row
      .map((value, index) => {
        const x = (index / (row.length - 1)) * (width - 4) + 2;
        const y = height - 4 - ((value - min) / span) * (height - 8);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      {comparison && comparison.length > 1 ? (
        <Polyline
          points={points(comparison)}
          fill="none"
          stroke={theme.textSecondary}
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      ) : null}
      <Polyline
        points={points(values)}
        fill="none"
        stroke={theme.accent}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </Svg>
  );
}
