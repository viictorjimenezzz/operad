/**
 * Per-algorithm layout resolver. Layouts are discovered at build time via
 * import.meta.glob — just drop a new `<algo>.json` into this directory and
 * it is automatically available without touching any other file.
 *
 * Resolution order: exact match on `algorithm_path` → prefix match →
 * `default.json` fallback.
 */
import { LayoutSpec } from "@/lib/layout-schema";

const modules = import.meta.glob("../layouts/*.json", {
  eager: true,
}) as Record<string, { default?: unknown } | unknown>;

const algorithmLayouts: Record<string, LayoutSpec> = {};
let defaultLayout: LayoutSpec | null = null;

for (const [path, mod] of Object.entries(modules)) {
  const raw = (mod as { default?: unknown }).default ?? mod;
  const parsed = LayoutSpec.parse(raw);
  if (path.endsWith("/default.json")) {
    defaultLayout = parsed;
  } else {
    algorithmLayouts[parsed.algorithm] = parsed;
  }
}

if (!defaultLayout) {
  throw new Error("layouts/default.json is required but was not found");
}

// biome-ignore lint/style/noNonNullAssertion: guarded by the throw above
const _defaultLayout: LayoutSpec = defaultLayout!;

export function resolveLayout(algorithmPath: string | null | undefined): LayoutSpec {
  if (!algorithmPath) return _defaultLayout;
  // Exact match
  const exact = algorithmLayouts[algorithmPath];
  if (exact) return exact;
  // Prefix match: "EvoGradient_v2" → "EvoGradient"
  const prefix = Object.keys(algorithmLayouts).find((k) => algorithmPath.startsWith(k));
  const prefixLayout = prefix !== undefined ? algorithmLayouts[prefix] : undefined;
  if (prefixLayout) return prefixLayout;
  return _defaultLayout;
}

/** @deprecated use resolveLayout */
export function pickLayout(algorithmPath: string | null | undefined): LayoutSpec {
  return resolveLayout(algorithmPath);
}

export const layouts: Record<string, LayoutSpec> = {
  default: _defaultLayout,
  ...algorithmLayouts,
};
