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
    Stack: { props: z.object({ gap: z.number().optional() }), hasChildren: true },
    SectionGroup: { props: z.object({}), hasChildren: true },
    Section: {
      props: z.object({
        title: z.string(),
        summary: z.string().optional(),
        defaultOpen: z.boolean().optional(),
        disabled: z.boolean().optional(),
      }),
      hasChildren: true,
    },
    PanelCard: {
      props: z.object({
        title: z.string().optional(),
        eyebrow: z.string().optional(),
        flush: z.boolean().optional(),
        bodyMinHeight: z.number().optional(),
        surface: z.enum(["panel", "inset"]).optional(),
        bare: z.boolean().optional(),
      }),
      hasChildren: true,
    },
    PanelGrid: {
      props: z.object({
        cols: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).optional(),
        gap: z.enum(["sm", "md", "lg"]).optional(),
      }),
      hasChildren: true,
    },
    PanelGridItem: {
      props: z.object({
        colSpan: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).optional(),
        rowSpan: z.union([z.literal(1), z.literal(2)]).optional(),
      }),
      hasChildren: true,
    },
    PanelSection: {
      props: z.object({ label: z.string(), count: z.number().optional() }),
      hasChildren: true,
    },
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
    DebateDetailOverview: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceDebate: sourceExpr,
        sourceChildren: sourceExpr,
        runId: z.string().optional(),
      }),
    },
    DebateRoundsTab: { props: z.object({ source: sourceExpr }) },
    DebateConsensusTab: { props: z.object({ source: sourceExpr }) },
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
    SelfRefineDetailOverview: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceIterations: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    IterationLadder: {
      props: z.object({
        source: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    SelfRefineConvergence: {
      props: z.object({ source: sourceExpr, height: z.number().optional() }),
    },
    AutoResearcherDetailOverview: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceIterations: sourceExpr,
        sourceEvents: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    AutoResearcherPlanTab: {
      props: z.object({
        sourceEvents: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    AutoResearcherAttemptsTab: {
      props: z.object({
        sourceIterations: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    AutoResearcherBestAnswer: {
      props: z.object({
        sourceChildren: sourceExpr,
      }),
    },
    SweepHeatmap: { props: z.object({ source: sourceExpr }) },
    SweepBestCellCard: { props: z.object({ source: sourceExpr }) },
    SweepCostTotalizer: { props: z.object({ source: sourceExpr }) },
    SweepDetailOverview: {
      props: z.object({
        source: sourceExpr,
        sourceSummary: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    SweepHeatmapTab: { props: z.object({ source: sourceExpr, sourceChildren: sourceExpr }) },
    SweepCellsTab: {
      props: z.object({
        source: sourceExpr,
        sourceChildren: sourceExpr,
        runId: z.string().optional(),
      }),
    },
    SweepCostTab: {
      props: z.object({
        source: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    BeamDetailOverview: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceIterations: sourceExpr,
        sourceChildren: sourceExpr,
      }),
    },
    BeamLeaderboard: {
      props: z.object({
        source: sourceExpr,
        sourceIterations: sourceExpr,
        sourceChildren: sourceExpr,
        runId: z.string().optional(),
      }),
    },
    BeamScoreHistogram: {
      props: z.object({
        source: sourceExpr,
        sourceIterations: sourceExpr,
      }),
    },
    VerifierDetailOverview: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceIterations: sourceExpr,
        runId: z.string().optional(),
      }),
    },
    VerifierIterationsTab: { props: z.object({ source: sourceExpr }) },
    VerifierAcceptanceTab: { props: z.object({ source: sourceExpr }) },
    AgentGraph: {
      props: z.object({
        source: sourceExpr,
        mutationsSource: sourceExpr,
      }),
    },
    AgentMetadataPanel: {
      props: z.object({
        sourceSummary: sourceExpr,
        sourceInvocations: sourceExpr,
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
    InteractiveGraph: {
      props: z.object({
        sourceIoGraph: sourceExpr,
        runId: z.string().optional(),
      }),
    },
    SideDrawer: {
      props: z.object({
        runId: z.string().optional(),
      }),
    },

    // Universal tabs
    AgentsTab: {
      props: z.object({
        runId: z.string().optional(),
        groupBy: z.enum(["hash", "none"]).optional(),
        extraColumns: z.array(z.string()).optional(),
        emptyTitle: z.string().optional(),
        emptyDescription: z.string().optional(),
      }),
    },
    EventsTab: {
      props: z.object({
        runId: z.string().optional(),
        defaultKindFilter: z.array(z.string()).optional(),
        defaultPathFilter: z.string().optional(),
      }),
    },

    // Diagnostics
    IODetail: { props: z.object({ source: sourceExpr }) },
    RawEnvelope: { props: z.object({}) },
  },
  actions: {},
});

export type OperadCatalog = typeof catalog;
