import Svg, { Circle, Line, Polyline, Text as SvgText } from "react-native-svg";

import { useTheme } from "@/hooks/use-theme";
import { shortDate } from "@/utils/date";
import { figure } from "@/utils/figures";

const WIDTH = 340;
const HEIGHT = 200;
const LEFT = 52;
const RIGHT = 52;
const TOP = 18;
const BOTTOM = 28;

export type DatedPoint = { date: string; value: number };

function bounds(values: number[]): [number, number] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return [min - 1, max + 1];
  const pad = (max - min) * 0.15;
  return [min - pad, max + pad];
}

function xAt(index: number, count: number): number {
  if (count <= 1) return LEFT + (WIDTH - LEFT - RIGHT) / 2;
  return LEFT + (index / (count - 1)) * (WIDTH - LEFT - RIGHT);
}

function yAt(value: number, min: number, max: number): number {
  const span = max - min || 1;
  return TOP + (1 - (value - min) / span) * (HEIGHT - TOP - BOTTOM);
}

function marked(count: number): number[] {
  if (count <= 1) return [0];
  const chosen = [0];
  for (let index = 1; index < count; index += 1) {
    const previous = xAt(chosen[chosen.length - 1], count);
    const x = xAt(index, count);
    const last = index === count - 1;
    if (last) {
      if (x - previous < 52 && chosen.length > 1) chosen.pop();
      chosen.push(index);
    } else if (x - previous >= 56 && xAt(count - 1, count) - x >= 56) {
      chosen.push(index);
    }
  }
  return chosen;
}

function line(values: (number | null)[], count: number, min: number, max: number): string[] {
  const parts: string[] = [];
  let current: string[] = [];
  values.forEach((value, index) => {
    if (value == null) {
      if (current.length > 1) parts.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${xAt(index, count).toFixed(1)},${yAt(value, min, max).toFixed(1)}`);
  });
  if (current.length > 1) parts.push(current.join(" "));
  return parts;
}

export function DatedChart({
  points,
  bodyweight,
}: {
  points: DatedPoint[];
  bodyweight: (number | null)[];
}) {
  const theme = useTheme();
  const count = points.length;
  if (count === 0) return null;
  const [low, high] = bounds(points.map((point) => point.value));
  const weights = bodyweight.filter((value): value is number => value != null);
  const weightScale = weights.length > 0 ? bounds(weights) : null;
  const labels = marked(count);
  const plotBottom = HEIGHT - BOTTOM;

  return (
    <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
      <Line x1={LEFT} y1={plotBottom} x2={WIDTH - RIGHT} y2={plotBottom} stroke={theme.separator} strokeWidth={1} />
      <SvgText x={8} y={TOP + 4} fill={theme.accent} fontSize={11}>
        {figure(high, 0)}
      </SvgText>
      <SvgText x={8} y={plotBottom} fill={theme.accent} fontSize={11}>
        {figure(low, 0)}
      </SvgText>
      {weightScale ? (
        <>
          <SvgText x={WIDTH - 8} y={TOP + 4} fill={theme.textSecondary} fontSize={11} textAnchor="end">
            {figure(weightScale[1], 0)}
          </SvgText>
          <SvgText x={WIDTH - 8} y={plotBottom} fill={theme.textSecondary} fontSize={11} textAnchor="end">
            {figure(weightScale[0], 0)}
          </SvgText>
        </>
      ) : null}
      {weightScale
        ? line(bodyweight, count, weightScale[0], weightScale[1]).map((pointsText) => (
            <Polyline
              key={`body-${pointsText}`}
              points={pointsText}
              fill="none"
              stroke={theme.textSecondary}
              strokeWidth={1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))
        : null}
      {line(
        points.map((point) => point.value),
        count,
        low,
        high,
      ).map((pointsText) => (
        <Polyline
          key={`lift-${pointsText}`}
          points={pointsText}
          fill="none"
          stroke={theme.accent}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      ))}
      {points.map((point, index) => {
        const x = xAt(index, count);
        const y = yAt(point.value, low, high);
        const show = labels.includes(index);
        return (
          <Circle key={point.date} cx={x} cy={y} r={show ? 3.5 : 2.5} fill={theme.accent} />
        );
      })}
      {labels.map((index) => {
        const point = points[index];
        const x = xAt(index, count);
        const y = yAt(point.value, low, high);
        const above = y > TOP + 18;
        const first = index === 0;
        const last = index === count - 1;
        const anchor = first ? "start" : last ? "end" : "middle";
        const labelX = first ? x + 6 : last ? x - 6 : x;
        return (
          <SvgText
            key={`${point.date}-value`}
            x={labelX}
            y={above ? y - 8 : y + 14}
            fill={theme.text}
            fontSize={11}
            textAnchor={anchor}>
            {figure(point.value)}
          </SvgText>
        );
      })}
      {labels.map((index) => (
        <SvgText
          key={`${points[index].date}-date`}
          x={xAt(index, count)}
          y={HEIGHT - 12}
          fill={theme.textSecondary}
          fontSize={11}
          textAnchor="middle">
          {shortDate(points[index].date)}
        </SvgText>
      ))}
    </Svg>
  );
}
