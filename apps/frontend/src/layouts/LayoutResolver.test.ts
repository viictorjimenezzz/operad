import type { LayoutSpec } from "@/lib/layout-schema";
import { describe, expect, it } from "vitest";

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
  agentLayout?: LayoutSpec,
): (algorithmPath: string | null | undefined) => LayoutSpec {
  return (algorithmPath) => {
    if (!algorithmPath) return agentLayout ?? fallback;
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
  const agents = makeLayout("*");
  const resolve = makeResolver({ EvoGradient: evo, Trainer: trainer }, dflt, agents);

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

  it("null returns agents layout", () => {
    expect(resolve(null)).toBe(agents);
  });

  it("undefined returns agents layout", () => {
    expect(resolve(undefined)).toBe(agents);
  });

  it("empty string returns agents layout", () => {
    expect(resolve("")).toBe(agents);
  });
});

describe("resolveLayout integration (real layouts/)", () => {
  it("resolves EvoGradient to the evogradient layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("EvoGradient");
    expect(layout.algorithm).toBe("EvoGradient");
  });

  it("resolves VerifierLoop to the verifier layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("VerifierLoop");
    expect(layout.algorithm).toBe("VerifierLoop");
  });

  it("resolves SelfRefine to the selfrefine layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("SelfRefine");
    expect(layout.algorithm).toBe("SelfRefine");
  });

  it("resolves unknown path to default layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("DoesNotExist");
    expect(layout.algorithm).toBe("__no_layout__");
  });

  it("resolves null to agents layout", async () => {
    const { resolveLayout } = await import("./index");
    expect(resolveLayout(null).algorithm).toBe("*");
  });

  it("resolves Sweep to the sweep layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("Sweep");
    expect(layout.algorithm).toBe("Sweep");
  });

  it("beam/verifier/selfrefine layouts reference iteration sources/components", async () => {
    const { resolveLayout } = await import("./index");
    const beam = resolveLayout("Beam");
    const verifier = resolveLayout("VerifierLoop");
    const selfrefine = resolveLayout("SelfRefine");

    expect(beam.dataSources.iterations?.endpoint).toContain("/iterations.json");
    expect(beam.spec.elements.candidates?.type).toBe("BeamCandidateChart");
    expect(verifier.spec.elements.curve?.type).toBe("ConvergenceCurve");
    expect(verifier.spec.elements.progression?.type).toBe("IterationProgression");
    expect(selfrefine.spec.elements.refinements?.type).toBe("IterationProgression");
    expect(selfrefine.spec.elements.refinements?.props?.showDiff).toBe(true);
  });
});
