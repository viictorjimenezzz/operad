import { describe, expect, it } from "vitest";
import type { LayoutSpec } from "@/lib/layout-schema";

/**
 * Test the resolution logic in isolation — we don't load real JSON files
 * here; instead we exercise the same algorithm used by resolveLayout().
 */
function makeLayout(algorithm: string): LayoutSpec {
  return {
    algorithm,
    version: 1,
    dataSources: {},
    spec: { root: "root", elements: { root: { type: "Col" } } },
  };
}

function makeResolver(
  reg: Record<string, LayoutSpec>,
  fallback: LayoutSpec,
): (algorithmPath: string | null | undefined) => LayoutSpec {
  return (algorithmPath) => {
    if (!algorithmPath) return fallback;
    const exact = reg[algorithmPath];
    if (exact) return exact;
    const prefix = Object.keys(reg).find((k) => algorithmPath.startsWith(k));
    const prefixLayout = prefix !== undefined ? reg[prefix] : undefined;
    if (prefixLayout) return prefixLayout;
    return fallback;
  };
}

describe("resolveLayout algorithm", () => {
  const evo = makeLayout("EvoGradient");
  const trainer = makeLayout("Trainer");
  const dflt = makeLayout("Default");
  const resolve = makeResolver({ EvoGradient: evo, Trainer: trainer }, dflt);

  it("exact match returns the correct layout", () => {
    expect(resolve("EvoGradient")).toBe(evo);
    expect(resolve("Trainer")).toBe(trainer);
  });

  it("prefix match returns the correct layout", () => {
    expect(resolve("EvoGradient_v2")).toBe(evo);
    expect(resolve("TrainerFast")).toBe(trainer);
  });

  it("unknown algorithm returns default", () => {
    expect(resolve("SomethingNew")).toBe(dflt);
  });

  it("null returns default", () => {
    expect(resolve(null)).toBe(dflt);
  });

  it("undefined returns default", () => {
    expect(resolve(undefined)).toBe(dflt);
  });

  it("empty string returns default", () => {
    expect(resolve("")).toBe(dflt);
  });
});

describe("resolveLayout integration (real layouts/)", () => {
  it("resolves EvoGradient to the evogradient layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("EvoGradient");
    expect(layout.algorithm).toBe("EvoGradient");
  });

  it("resolves unknown path to default layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("DoesNotExist");
    expect(layout.algorithm).toBe("*");
  });

  it("resolves null to default layout", async () => {
    const { resolveLayout } = await import("./index");
    expect(resolveLayout(null).algorithm).toBe("*");
  });
});
