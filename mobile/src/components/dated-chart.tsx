import { View } from "react-native";
import Svg, { Circle, G, Line, Polyline, Text as SvgText } from "react-native-svg";

import { ThemedText } from "@/components/themed-text";
import { Spacing } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

const WIDTH = 360;
const HEIGHT = 232;
const LEFT = 48;
const RIGHT = 14;
const TOP = 14;
const BOTTOM = 32;
const DAY = 86400000;

export type DatedPoint = { date: string; value: number };
export type DatedSeries = { label: string; color: string; points: DatedPoint[] };

function time(iso: string): number {
  const [year, month, day] = iso.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function niceStep(span: number): number {
  const rough = Math.max(span, 1e-6) / 4;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const fraction = rough / pow;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * pow;
}

function scale(values: number[]): { low: number; high: number; ticks: number[] } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const step = niceStep(max === min ? 2 : max - min);
  const low = Math.floor(min / step) * step;
  const high = Math.max(low + step, Math.ceil(max / step) * step);
  const count = Math.round((high - low) / step);
  const ticks = Array.from({ length: count + 1 }, (_, index) => Math.round((low + index * step) * 1000) / 1000);
  return { low, high, ticks };
}

function xLabels(start: number, end: number): number[] {
  if (end <= start) return [start];
  const slots = end - start > 180 * DAY ? 3 : 4;
  return Array.from({ length: slots }, (_, index) => start + ((end - start) * index) / (slots - 1));
}

function dateLabel(stamp: number, start: number, end: number, edge: boolean): string {
  const value = new Date(stamp);
  const month = value.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
  const day = value.getUTCDate();
  const year = value.getUTCFullYear();
  if (edge || end - start > 180 * DAY) {
    return edge ? `${month} ${day}, ${year}` : `${month} ${year}`;
  }
  return `${month} ${day}`;
}

function yAt(value: number, low: number, high: number): number {
  const span = high - low || 1;
  return TOP + (1 - (value - low) / span) * (HEIGHT - TOP - BOTTOM);
}

function xAt(stamp: number, start: number, end: number): number {
  const width = WIDTH - LEFT - RIGHT;
  if (end <= start) return LEFT + width / 2;
  return LEFT + ((stamp - start) / (end - start)) * width;
}

function tickText(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
}

function ordered(points: DatedPoint[]): DatedPoint[] {
  return [...points].sort((left, right) => left.date.localeCompare(right.date));
}

export function DatedChart({ series }: { series: DatedSeries[] }) {
  const theme = useTheme();
  const drawn = series
    .map((item) => ({ ...item, points: ordered(item.points) }))
    .filter((item) => item.points.length > 0);
  const flat = drawn.flatMap((item) => item.points);
  if (flat.length === 0) return null;
  const stamps = flat.map((point) => time(point.date));
  const start = Math.min(...stamps);
  const end = Math.max(...stamps);
  const { low, high, ticks } = scale(flat.map((point) => point.value));
  const labels = xLabels(start, end);

  return (
    <View style={{ gap: Spacing.two }}>
      <View style={{ flexDirection: "row", gap: Spacing.three }}>
        {drawn.map((item) => (
          <ThemedText key={item.label} type="small" style={{ color: item.color }}>
            {item.label}
          </ThemedText>
        ))}
        <ThemedText type="small" themeColor="textSecondary">
          lb
        </ThemedText>
      </View>
      <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        {ticks.map((tick) => (
          <Line
            key={tick}
            x1={LEFT}
            y1={yAt(tick, low, high)}
            x2={WIDTH - RIGHT}
            y2={yAt(tick, low, high)}
            stroke={theme.separator}
            strokeWidth={1}
          />
        ))}
        {ticks.map((tick) => (
          <SvgText
            key={`label-${tick}`}
            x={LEFT - 8}
            y={yAt(tick, low, high) + 4}
            fill={theme.textSecondary}
            fontSize={12}
            textAnchor="end">
            {tickText(tick)}
          </SvgText>
        ))}
        {drawn.map((item, index) => {
          if (item.points.length < 2) return null;
          const points = item.points
            .map((point) => `${xAt(time(point.date), start, end).toFixed(1)},${yAt(point.value, low, high).toFixed(1)}`)
            .join(" ");
          return (
            <Polyline
              key={item.label}
              points={points}
              fill="none"
              stroke={item.color}
              strokeWidth={index === 0 ? 2.25 : 1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          );
        })}
        {drawn.map((item) => {
          const last = item.points[item.points.length - 1];
          const cx = xAt(time(last.date), start, end);
          const cy = yAt(last.value, low, high);
          const lower = drawn.some((other) => {
            if (other === item) return false;
            const endPoint = other.points[other.points.length - 1];
            return yAt(endPoint.value, low, high) < cy;
          });
          const labelY = lower ? Math.min(cy + 14, HEIGHT - BOTTOM - 2) : Math.max(cy - 8, 12);
          return (
            <G key={`${item.label}-last`}>
              <Circle cx={cx} cy={cy} r={4} fill={item.color} />
              <SvgText x={cx - 6} y={labelY} fill={item.color} fontSize={12} textAnchor="end">
                {tickText(last.value)}
              </SvgText>
            </G>
          );
        })}
        {labels.map((stamp, index) => {
          const first = index === 0;
          const last = index === labels.length - 1;
          return (
            <SvgText
              key={stamp}
              x={first ? LEFT : last ? WIDTH - RIGHT : xAt(stamp, start, end)}
              y={HEIGHT - 8}
              fill={theme.textSecondary}
              fontSize={12}
              textAnchor={first ? "start" : last ? "end" : "middle"}>
              {dateLabel(stamp, start, end, first || last)}
            </SvgText>
          );
        })}
      </Svg>
    </View>
  );
}
