/**
 * Zod schemas mirroring the wire envelopes that operad's
 * WebDashboardObserver / dashboard.attach() emit. Source of truth for
 * the shapes:
 *  - apps/dashboard/operad_dashboard/observer.py:serialize_event
 *  - apps/dashboard/operad_dashboard/runs.py:RunInfo.summary
 *  - apps/dashboard/operad_dashboard/routes/{fitness,mutations,drift,progress}.py
 *
 * Every fetch hook + the SSE dispatcher parses through these.
 */
import { z } from "zod";

const numberOrNull = z.number().nullable();
const stringOrNull = z.string().nullable();

// --- Envelopes (SSE union) ---------------------------------------------------

export const AgentEventEnvelope = z.object({
  type: z.literal("agent_event"),
  run_id: z.string(),
  agent_path: z.string(),
  kind: z.enum(["start", "end", "error", "chunk"]),
  input: z.unknown().nullable(),
  output: z.unknown().nullable(),
  started_at: z.number(),
  finished_at: numberOrNull,
  metadata: z.record(z.unknown()).default({}),
  error: z.object({ type: z.string(), message: z.string() }).nullable().default(null),
});
export type AgentEventEnvelope = z.infer<typeof AgentEventEnvelope>;

export const AlgoEventEnvelope = z.object({
  type: z.literal("algo_event"),
  run_id: z.string(),
  algorithm_path: z.string(),
  kind: z.string(),
  payload: z.record(z.unknown()).default({}),
  started_at: z.number(),
  finished_at: numberOrNull,
  metadata: z.record(z.unknown()).default({}),
});
export type AlgoEventEnvelope = z.infer<typeof AlgoEventEnvelope>;

export const SlotOccupancyEntry = z.object({
  backend: z.string(),
  host: z.string(),
  concurrency_used: z.number().optional(),
  concurrency_limit: z.number().nullable().optional(),
  rpm_used: z.number().optional(),
  rpm_limit: z.number().nullable().optional(),
  tpm_used: z.number().optional(),
  tpm_limit: z.number().nullable().optional(),
});
export type SlotOccupancyEntry = z.infer<typeof SlotOccupancyEntry>;

export const SlotOccupancyEnvelope = z.object({
  type: z.literal("slot_occupancy"),
  snapshot: z.array(SlotOccupancyEntry),
});
export type SlotOccupancyEnvelope = z.infer<typeof SlotOccupancyEnvelope>;

export const CostTotals = z.object({
  prompt_tokens: z.number().default(0),
  completion_tokens: z.number().default(0),
  cost_usd: z.number().default(0),
});
export type CostTotals = z.infer<typeof CostTotals>;

export const CostUpdateEnvelope = z.object({
  type: z.literal("cost_update"),
  totals: z.record(CostTotals).default({}),
});
export type CostUpdateEnvelope = z.infer<typeof CostUpdateEnvelope>;

export const GlobalStats = z.object({
  runs_total: z.number().default(0),
  runs_running: z.number().default(0),
  runs_ended: z.number().default(0),
  runs_error: z.number().default(0),
  runs_algorithm: z.number().default(0),
  runs_agent: z.number().default(0),
  event_total: z.number().default(0),
  prompt_tokens: z.number().default(0),
  completion_tokens: z.number().default(0),
  subscribers: z.number().optional(),
});
export type GlobalStats = z.infer<typeof GlobalStats>;

export const StatsUpdateEnvelope = z.object({
  type: z.literal("stats_update"),
  stats: GlobalStats,
});
export type StatsUpdateEnvelope = z.infer<typeof StatsUpdateEnvelope>;

export const Envelope = z.discriminatedUnion("type", [
  AgentEventEnvelope,
  AlgoEventEnvelope,
  SlotOccupancyEnvelope,
  CostUpdateEnvelope,
  StatsUpdateEnvelope,
]);
export type Envelope = z.infer<typeof Envelope>;

export type EventEnvelope = AgentEventEnvelope | AlgoEventEnvelope;

// --- Run summary -------------------------------------------------------------

export const Generation = z.object({
  gen_index: z.number().nullable(),
  best: numberOrNull,
  mean: numberOrNull,
  scores: z.array(z.number()).default([]),
  survivor_indices: z.array(z.number()).default([]),
  op_attempt_counts: z.record(z.number()).default({}),
  op_success_counts: z.record(z.number()).default({}),
  timestamp: numberOrNull,
});
export type Generation = z.infer<typeof Generation>;

export const Iteration = z.object({
  iter_index: z.number().nullable(),
  phase: stringOrNull,
  score: numberOrNull,
  timestamp: numberOrNull,
});
export type Iteration = z.infer<typeof Iteration>;

export const Round = z.object({
  round_index: z.number().nullable(),
  scores: z.array(z.number()).default([]),
  timestamp: numberOrNull,
});
export type Round = z.infer<typeof Round>;

export const Candidate = z.object({
  candidate_index: z.number().nullable(),
  score: numberOrNull,
  timestamp: numberOrNull,
});
export type Candidate = z.infer<typeof Candidate>;

export const Batch = z.object({
  kind: z.string(),
  batch_index: z.number().nullable(),
  batch_size: z.number().nullable(),
  duration_ms: numberOrNull,
  epoch: z.number().nullable(),
  timestamp: numberOrNull,
});
export type Batch = z.infer<typeof Batch>;

export const RunSummary = z.object({
  run_id: z.string(),
  started_at: z.number(),
  last_event_at: z.number(),
  state: z.enum(["running", "ended", "error"]),
  has_graph: z.boolean(),
  is_algorithm: z.boolean(),
  algorithm_path: stringOrNull,
  algorithm_kinds: z.array(z.string()).default([]),
  root_agent_path: stringOrNull,
  event_counts: z.record(z.number()).default({}),
  event_total: z.number(),
  duration_ms: z.number(),
  generations: z.array(Generation).default([]),
  iterations: z.array(Iteration).default([]),
  rounds: z.array(Round).default([]),
  candidates: z.array(Candidate).default([]),
  batches: z.array(Batch).default([]),
  prompt_tokens: z.number().default(0),
  completion_tokens: z.number().default(0),
  error: stringOrNull,
  algorithm_terminal_score: numberOrNull,
  cost: CostTotals.optional(),
  synthetic: z.boolean().default(false),
  parent_run_id: stringOrNull.default(null),
  algorithm_class: stringOrNull.default(null),
});
export type RunSummary = z.infer<typeof RunSummary>;

// --- Panel shapes ------------------------------------------------------------

export const FitnessEntry = z.object({
  gen_index: z.number(),
  best: z.number(),
  mean: z.number(),
  worst: z.number(),
  population_scores: z.array(z.number()),
  timestamp: z.number(),
});
export type FitnessEntry = z.infer<typeof FitnessEntry>;

export const MutationsMatrix = z.object({
  gens: z.array(z.number()),
  ops: z.array(z.string()),
  success: z.array(z.array(z.number())),
  attempts: z.array(z.array(z.number())),
});
export type MutationsMatrix = z.infer<typeof MutationsMatrix>;

export const DriftEntry = z.object({
  epoch: z.number(),
  hash_before: z.string(),
  hash_after: z.string(),
  changed_params: z.array(z.string()),
  delta_count: z.number(),
  timestamp: z.number(),
});
export type DriftEntry = z.infer<typeof DriftEntry>;

export const ProgressSnapshot = z.object({
  epoch: z.number(),
  epochs_total: z.number().nullable(),
  batch: z.number(),
  batches_total: z.number().nullable(),
  elapsed_s: z.number(),
  rate_batches_per_s: z.number(),
  eta_s: z.number().nullable(),
  finished: z.boolean(),
});
export type ProgressSnapshot = z.infer<typeof ProgressSnapshot>;

// --- Debate panel shapes -----------------------------------------------------

export const DebateProposal = z.object({
  content: z.string().default(""),
  author: z.string().default(""),
});
export type DebateProposal = z.infer<typeof DebateProposal>;

export const DebateCritique = z.object({
  target_author: z.string().default(""),
  comments: z.string().default(""),
  score: z.number().default(0),
});
export type DebateCritique = z.infer<typeof DebateCritique>;

export const DebateRound = z.object({
  round_index: z.number().nullable(),
  proposals: z.array(DebateProposal).default([]),
  critiques: z.array(DebateCritique).default([]),
  scores: z.array(z.number()).default([]),
  timestamp: z.number().nullable(),
});
export type DebateRound = z.infer<typeof DebateRound>;

export const DebateRoundsResponse = z.array(DebateRound);
export type DebateRoundsResponse = z.infer<typeof DebateRoundsResponse>;

export const GraphResponse = z.object({ mermaid: z.string() });
export type GraphResponse = z.infer<typeof GraphResponse>;

export const RunEventsResponse = z.object({
  run_id: z.string(),
  events: z.array(Envelope),
});
export type RunEventsResponse = z.infer<typeof RunEventsResponse>;

export const StatsResponse = GlobalStats.extend({
  cost_totals: z.record(CostTotals).default({}),
});
export type StatsResponse = z.infer<typeof StatsResponse>;

export const EvolutionResponse = z.object({
  generations: z.array(Generation.extend({ run_id: z.string(), algorithm_path: stringOrNull })),
});
export type EvolutionResponse = z.infer<typeof EvolutionResponse>;

// --- Studio shapes -----------------------------------------------------------

export const JobSummary = z.object({
  name: z.string(),
  total_rows: z.number(),
  rated_rows: z.number(),
  unrated: z.number(),
});
export type JobSummary = z.infer<typeof JobSummary>;

export const JobRow = z.object({
  id: z.string(),
  index: z.number(),
  run_id: z.string(),
  agent_path: z.string(),
  input: z.unknown(),
  expected: z.unknown(),
  predicted: z.unknown(),
  rating: z.number().nullable(),
  rationale: stringOrNull,
  written_at: z.string(),
});
export type JobRow = z.infer<typeof JobRow>;

export const JobDetailResponse = z.object({
  rows: z.array(JobRow),
  total: z.number(),
  rated: z.number(),
});
export type JobDetailResponse = z.infer<typeof JobDetailResponse>;

export const TrainingEvent = z
  .object({
    kind: z.string(),
    job_name: z.string().optional(),
    message: z.string().optional(),
    timestamp: z.number().optional(),
  })
  .passthrough();
export type TrainingEvent = z.infer<typeof TrainingEvent>;

// --- Manifest ---------------------------------------------------------------

export const Manifest = z.object({
  mode: z.enum(["dashboard", "studio"]),
  langfuseUrl: z.string().nullable().optional(),
  dashboardPort: z.number().nullable().optional(),
  dataDir: z.string().optional(),
  version: z.string().optional(),
});
export type Manifest = z.infer<typeof Manifest>;
