export function figure(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  const factor = 10 ** digits;
  const rounded = Math.round(value * factor) / factor;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(digits);
}

export function signed(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  const text = figure(Math.abs(value), digits);
  if (value > 0) return `+${text}`;
  if (value < 0) return `−${text}`;
  return text;
}
