/**
 * @json-render catalog: every component the layout JSONs are allowed
 * to reference, with Zod prop schemas. Catalog membership + the prop
 * shape are validated at typecheck time and again at render time.
 *
 * Adding a new component means:
 *  1. add an entry here,
 *  2. add the implementation in src/registry/registry.tsx, and
 *  3. add a Vitest layout-schema test if it's referenced in any
 *     layouts/*.json.
 */
import { createCatalog } from "@json-render/core";
import { z } from "zod";

const sourceProp = z.union([z.string(), z.unknown()]).optional();
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

    // Header / KPI tiles
    KPI: {
      props: z.object({
        label: z.string(),
        source: sourceProp,
        format: z.enum(["int", "duration", "cost", "tokens", "number", "string"]).optional(),
        sub: z.string().optional(),
      }),
    },
    MetaList: { props: z.object({ source: sourceProp }) },
    LangfuseLink: { props: z.object({ runId: sourceProp }) },

    // Charts
    FitnessCurve: { props: z.object({ source: sourceProp, height: z.number().optional() }) },
    PopulationScatter: { props: z.object({ source: sourceProp, height: z.number().optional() }) },
    MutationHeatmap: { props: z.object({ source: sourceProp }) },
    OpSuccessTable: { props: z.object({ source: sourceProp }) },
    TrainingProgress: { props: z.object({ source: sourceProp }) },
    TrainingLossCurve: { props: z.object({ source: sourceProp, height: z.number().optional() }) },
    DriftTimeline: { props: z.object({ source: sourceProp }) },
    DebateRoundView: { props: z.object({ source: sourceProp }) },
    BeamCandidateChart: { props: z.object({ source: sourceProp, height: z.number().optional() }) },
    AgentGraph: {
      props: z.object({
        source: sourceProp,
        mutationsSource: sourceProp,
      }),
    },

    // Diagnostics
    EventTimeline: {
      props: z.object({
        source: sourceProp,
        kindFilter: z.string().optional(),
      }),
    },
    IODetail: { props: z.object({ source: sourceProp }) },
    RawEnvelope: { props: z.object({}) },
  },
  actions: {},
});

export type OperadCatalog = typeof catalog;
