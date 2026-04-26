/**
 * @json-render catalog: every component the layout JSONs are allowed
 * to reference, with Zod prop schemas. Catalog membership + the prop
 * shape are validated at typecheck time and again at render time.
 *
 * Adding a new component means:
 *  1. add an entry here,
 *  2. add the implementation in per-folder `registry.tsx` files, and
 *  3. add a Vitest layout-schema test if it's referenced in any
 *     layouts/*.json.
 */
import { createCatalog } from "@json-render/core";
import { z } from "zod";

const sourceExpr = z.string().optional();
const tab = z.object({ id: z.string(), label: z.string() });

export const catalog = createCatalog({
  name: "operad-dashboard",
  components: {
    // Layout primitives
    Card: { props: z.object({ title: z.string().optional() }), hasChildren: true },
    Row: { props: z.object({ gap: z.number().optional() }), hasChildren: true },
    Col: { props: z.object({ gap: z.number().optional() }), hasChildren: true },
    Tabs: {
      props: z.object({ tabs: z.array(tab) }),
      hasChildren: true,
      description: "Tab container; children render in tab order",
    },
    EmptyState: {
      props: z.object({
        title: z.string().optional(),
        description: z.string().optional(),
      }),
    },

    // Header / KPI tiles
    KPI: {
      props: z.object({
        label: z.string(),
        source: sourceExpr,
        format: z.enum(["int", "duration", "cost", "tokens", "number", "string"]).optional(),
        sub: z.string().optional(),
      }),
    },
    MetaList: { props: z.object({ source: sourceExpr }) },
    LangfuseLink: { props: z.object({ runId: z.string().optional() }) },
    LangfuseSummaryCard: { props: z.object({ runId: z.string().optional(), source: sourceExpr }) },

    // Charts
    FitnessCurve: { props: z.object({ source: sourceExpr, height: z.number().optional() }) },
    PopulationScatter: { props: z.object({ source: sourceExpr, height: z.number().optional() }) },
    MutationHeatmap: { props: z.object({ source: sourceExpr }) },
    OpSuccessTable: { props: z.object({ source: sourceExpr }) },
    TrainingProgress: { props: z.object({ source: sourceExpr }) },
    TrainingLossCurve: {
      props: z.object({
        source: sourceExpr,
        checkpointSource: sourceExpr,
        height: z.number().optional(),
      }),
    },
    DriftTimeline: { props: z.object({ source: sourceExpr }) },
    GradientLog: { props: z.object({ source: sourceExpr }) },
    LrScheduleCurve: { props: z.object({ source: sourceExpr, height: z.number().optional() }) },
    CheckpointTimeline: { props: z.object({ source: sourceExpr }) },
    DebateRoundView: { props: z.object({ source: sourceExpr }) },
    BeamCandidateChart: {
      props: z.object({
        source: sourceExpr,
        iterationsSource: sourceExpr,
        height: z.number().optional(),
      }),
    },
    ConvergenceCurve: {
      props: z.object({ source: sourceExpr, height: z.number().optional() }),
    },
    IterationProgression: {
      props: z.object({
        source: sourceExpr,
        phaseFilter: z.string().optional(),
        showDiff: z.boolean().optional(),
      }),
    },
    SweepHeatmap: { props: z.object({ source: sourceExpr }) },
    SweepBestCellCard: { props: z.object({ source: sourceExpr }) },
    SweepCostTotalizer: { props: z.object({ source: sourceExpr }) },
    AgentGraph: {
      props: z.object({
        source: sourceExpr,
        mutationsSource: sourceExpr,
      }),
    },
    AgentInsightsRow: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceInvocations: sourceExpr,
        runId: z.string().optional(),
        summary: z.unknown().optional(),
        invocations: z.unknown().optional(),
      }),
    },
    ValueDistribution: {
      props: z.object({
        source: sourceExpr,
        label: z.string().optional(),
        agentPath: z.string().optional(),
        side: z.enum(["in", "out"]).optional(),
      }),
    },

    // Diagnostics
    EventTimeline: {
      props: z.object({
        source: sourceExpr,
        kindFilter: z.string().optional(),
      }),
    },
    IODetail: { props: z.object({ source: sourceExpr }) },
    RawEnvelope: { props: z.object({}) },
  },
  actions: {},
});

export type OperadCatalog = typeof catalog;
