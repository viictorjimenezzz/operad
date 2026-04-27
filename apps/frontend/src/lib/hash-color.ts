/**
 * Deterministic, identity-based color mapping.
 *
 * The dashboard uses color as the primary visual hook between the sidebar
 * tree and every chart on the right: a group/instance/run keeps the same
 * hue everywhere it appears. Picking a curated palette (rather than a
 * raw HSL hash) gives consistent vibrance across the dark theme and lets
 * us reason about a fixed visual budget per panel.
 *
 * The palette is large enough that colliding within a single workspace
 * is unlikely; when it happens, two different `hash_content`s simply
 * share a color — same as W&B.
 */

export const SERIES_PALETTE = [
  "#6BC4FF", // sky
  "#A78BFA", // violet
  "#43C871", // emerald
  "#F2A93A", // amber
  "#FF6B7A", // rose
  "#5AA9FF", // azure
  "#34D2C8", // teal
  "#F26FCB", // pink
  "#9CD06D", // lime
  "#FFC857", // gold
  "#7CB9FF", // light azure
  "#B794F4", // mauve
] as const;

export type SeriesColor = (typeof SERIES_PALETTE)[number];

/**
 * Hash a string into a stable 32-bit integer. FNV-1a-ish; not crypto.
 */
function fold(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Map an arbitrary identity string to a curated palette color.
 * Two equal inputs always yield the same color.
 */
export function hashColor(value: string | null | undefined): string {
  if (!value) return "var(--color-muted-2)";
  const idx = fold(value) % SERIES_PALETTE.length;
  return SERIES_PALETTE[idx] as string;
}

/**
 * A dim variant of the same hue, suitable for fills and backgrounds.
 * Returns an rgba() with low alpha over the base color.
 */
export function hashColorDim(value: string | null | undefined, alpha = 0.18): string {
  const base = hashColor(value);
  if (base.startsWith("#")) return hexWithAlpha(base, alpha);
  return base;
}

/**
 * Stronger glow for the running-state pulse around a dot.
 */
export function hashColorGlow(value: string | null | undefined): string {
  const base = hashColor(value);
  return base.startsWith("#") ? hexWithAlpha(base, 0.55) : base;
}

function hexWithAlpha(hex: string, alpha: number): string {
  const v = hex.replace("#", "");
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
}

/**
 * Pick a deterministic palette index (used by tests + chart legends to
 * derive the same color without re-hashing).
 */
export function paletteIndex(value: string | null | undefined): number {
  if (!value) return -1;
  return fold(value) % SERIES_PALETTE.length;
}

/**
 * Backwards-compat name used elsewhere in the codebase. We keep it
 * pointing at the curated palette now.
 */
export function hashToHue(value: string): number {
  return fold(value) % 360;
}
