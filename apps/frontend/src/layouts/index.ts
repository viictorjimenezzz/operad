/**
 * Per-algorithm layout resolver. Layouts are discovered at build time via
 * import.meta.glob — just drop a new `<algo>.json` into this directory and
 * it is automatically available without touching any other file.
 *
 * Resolution order: exact match on `algorithm_path` → prefix match →
 * empty fallback layout.
 */
import { LayoutSpec } from "@/lib/layout-schema";

const modules = import.meta.glob("../layouts/*.json", {
  eager: true,
}) as Record<string, { default?: unknown } | unknown>;

const algorithmLayouts: Record<string, LayoutSpec> = {};
const fallbackLayout: LayoutSpec = {
  algorithm: "__no_layout__",
  version: 1,
  dataSources: {},
  spec: {
    root: "no-layout",
    elements: {
      "no-layout": {
        type: "EmptyState",
        props: {
          title: "no layout available",
          description: "this run type does not have a registered dashboard layout yet",
        },
      },
    },
  },
};

for (const [, mod] of Object.entries(modules)) {
  const raw = (mod as { default?: unknown }).default ?? mod;
  const parsed = LayoutSpec.parse(raw);
  algorithmLayouts[parsed.algorithm] = parsed;
}

export function resolveLayout(algorithmPath: string | null | undefined): LayoutSpec {
  if (!algorithmPath) return fallbackLayout;
  // Exact match
  const exact = algorithmLayouts[algorithmPath];
  if (exact) return exact;
  // Prefix match: "EvoGradient_v2" → "EvoGradient"
  const prefix = Object.keys(algorithmLayouts).find((k) => algorithmPath.startsWith(k));
  const prefixLayout = prefix !== undefined ? algorithmLayouts[prefix] : undefined;
  if (prefixLayout) return prefixLayout;
  return fallbackLayout;
}

/** @deprecated use resolveLayout */
export function pickLayout(algorithmPath: string | null | undefined): LayoutSpec {
  return resolveLayout(algorithmPath);
}

export const layouts: Record<string, LayoutSpec> = {
  default: fallbackLayout,
  ...algorithmLayouts,
};
