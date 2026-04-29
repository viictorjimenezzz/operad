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
  it("falls back to no_layout for null algorithm path", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout(null);
    expect(layout.algorithm).toBe("__no_layout__");
  });

  it("resolves EvoGradient to the evogradient layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("EvoGradient");
    expect(layout.algorithm).toBe("EvoGradient");
  });

  it("resolves VerifierAgent to the verifier layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("VerifierAgent");
    expect(layout.algorithm).toBe("VerifierAgent");
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

  it("resolves Sweep to the sweep layout", async () => {
    const { resolveLayout } = await import("./index");
    const layout = resolveLayout("Sweep");
    expect(layout.algorithm).toBe("Sweep");
  });

  it("resolves TalkerReasoner, AutoResearcher, and OPRO layouts", async () => {
    const { resolveLayout } = await import("./index");
    expect(resolveLayout("TalkerReasoner").algorithm).toBe("TalkerReasoner");
    expect(resolveLayout("AutoResearcher").algorithm).toBe("AutoResearcher");
    expect(resolveLayout("OPRO").algorithm).toBe("OPRO");
    expect(resolveLayout("OPROOptimizer").algorithm).toBe("OPRO");
  });

  it("beam/verifier/selfrefine layouts reference iteration sources/components", async () => {
    const { resolveLayout } = await import("./index");
    const beam = resolveLayout("Beam");
    const verifier = resolveLayout("VerifierAgent");
    const selfrefine = resolveLayout("SelfRefine");

    expect(beam.dataSources.iterations?.endpoint).toContain("/iterations.json");
    expect(beam.spec.elements.leaderboard?.type).toBe("BeamLeaderboardTab");
    expect(beam.spec.elements.candidates?.type).toBe("BeamCandidatesTab");
    expect(beam.spec.elements.histogram?.type).toBe("BeamHistogramTab");
    expect(verifier.spec.elements.iterations?.type).toBe("VerifierIterationsTab");
    expect(verifier.spec.elements.acceptance?.type).toBe("VerifierAcceptanceTab");
    expect(verifier.spec.elements.parameters?.type).toBe("ParametersTab");
    expect(selfrefine.dataSources.iterations?.endpoint).toContain("/iterations.json");
    expect(selfrefine.spec.elements.ladder?.type).toBe("SelfRefineLadderTab");
    expect(selfrefine.spec.elements.iterations?.type).toBe("SelfRefineIterationsTab");
  });

  it("debate and autoresearcher layouts expose their algorithm-specific tabs", async () => {
    const { resolveLayout } = await import("./index");
    const debate = resolveLayout("Debate");
    const autoResearcher = resolveLayout("AutoResearcher");

    expect(debate.dataSources.debate?.endpoint).toContain("/debate.json");
    expect(debate.spec.elements.rounds?.type).toBe("DebateRoundsTab");
    expect(debate.spec.elements.transcript?.type).toBe("DebateTranscriptTab");
    expect(debate.spec.elements.consensus?.type).toBe("DebateConsensusTab");
    expect((debate.spec.elements.agents?.props as { groupBy?: string }).groupBy).toBe("none");
    expect(
      ((debate.spec.elements.page?.props as { tabs?: Array<{ id: string }> }).tabs ?? []).map(
        (tab) => tab.id,
      ),
    ).toEqual(["rounds", "transcript", "consensus", "agents", "events"]);
    expect(autoResearcher.dataSources.iterations?.endpoint).toContain("/iterations.json");
    expect(autoResearcher.dataSources.runEvents?.endpoint).toContain("/events");
    expect(autoResearcher.spec.elements.plan?.type).toBe("AutoResearcherPlanTab");
    expect(autoResearcher.spec.elements.attempts?.type).toBe("AutoResearcherAttemptsTab");
  });

  it("registers every reserved per-algorithm component type", async () => {
    const { algorithmsRegistry } = await import("@/components/algorithms/registry");
    expect(Object.keys(algorithmsRegistry)).toEqual(
      expect.arrayContaining([
        "SweepDetailOverview",
        "SweepHeatmapTab",
        "SweepCellsTab",
        "SweepCostTab",
        "SweepParallelCoordsTab",
        "BeamLeaderboardTab",
        "BeamCandidatesTab",
        "BeamHistogramTab",
        "DebateRoundsTab",
        "DebateTranscriptTab",
        "DebateConsensusTab",
        "EvoLineageTab",
        "EvoPopulationTab",
        "EvoOperatorsTab",
        "TrainerLossTab",
        "TrainerScheduleTab",
        "TrainerDriftTab",
        "TrainerTracebackTab",
        "OPROPromptHistoryTab",
        "OPROScoreCurveTab",
        "SelfRefineLadderTab",
        "SelfRefineIterationsTab",
        "AutoResearcherPlanTab",
        "AutoResearcherAttemptsTab",
        "AutoResearcherBestTab",
        "TalkerTreeTab",
        "TalkerTranscriptTab",
        "TalkerDecisionsTab",
        "VerifierIterationsTab",
        "VerifierAcceptanceTab",
      ]),
    );
  }, 10_000);
});
