const PALETTE_SIZE = 12;

export const SERIES_PALETTE = Array.from(
  { length: PALETTE_SIZE },
  (_, i) => `var(--qual-${i + 1})`,
) as [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
];

export type SeriesColor = (typeof SERIES_PALETTE)[number];

function fold(identity: string): number {
  let h = 0;
  for (let i = 0; i < identity.length; i += 1) {
    h = (h * 31 + identity.charCodeAt(i)) | 0;
  }
  return h;
}

export function hashColor(identity: string | null | undefined): string {
  if (!identity) return "var(--qual-7)";
  return `var(--qual-${paletteIndex(identity) + 1})`;
}

export function hashColorDim(value: string | null | undefined, alpha = 0.18): string {
  return `color-mix(in srgb, ${hashColor(value)} ${Math.round(alpha * 100)}%, transparent)`;
}

export function hashColorGlow(value: string | null | undefined): string {
  return hashColorDim(value, 0.55);
}

export function paletteIndex(value: string | null | undefined): number {
  if (!value) return -1;
  const h = fold(value);
  return ((h % PALETTE_SIZE) + PALETTE_SIZE) % PALETTE_SIZE;
}
