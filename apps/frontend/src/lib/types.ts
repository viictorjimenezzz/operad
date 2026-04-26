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
  text: stringOrNull.default(null),
  metadata: z.record(z.unknown()).default({}),
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
  iter_index: z.number().nullable().default(null),
  candidate_index: z.number().nullable(),
  score: numberOrNull,
  text: stringOrNull.default(null),
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
  script: stringOrNull.default(null),
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
  train_loss: z.number().nullable().optional(),
  val_loss: z.number().nullable().optional(),
  lr: z.number().nullable().optional(),
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

export const DriftChange = z.object({
  path: z.string(),
  before_text: z.string(),
  after_text: z.string(),
});
export type DriftChange = z.infer<typeof DriftChange>;

export const DriftEntry = z.object({
  epoch: z.number(),
  before_text: z.string(),
  after_text: z.string(),
  selected_path: z.string(),
  changes: z.array(DriftChange),
  critique: z.string().default(""),
  gradient_epoch: z.number().nullable().default(null),
  gradient_batch: z.number().nullable().default(null),
  changed_params: z.array(z.string()),
  delta_count: z.number(),
  timestamp: z.number(),
});
export type DriftEntry = z.infer<typeof DriftEntry>;

export const CheckpointEntry = z.object({
  epoch: z.number(),
  train_loss: z.number().nullable(),
  val_loss: z.number().nullable(),
  score: z.number().nullable(),
  lr: z.number().nullable().optional(),
  metric_snapshot: z
    .object({
      train_loss: z.number().nullable(),
      val_loss: z.number().nullable(),
      score: z.number().nullable(),
    })
    .optional(),
  parameter_snapshot: z.record(z.string()).optional(),
  is_best: z.boolean(),
});
export type CheckpointEntry = z.infer<typeof CheckpointEntry>;

export const GradientEntry = z.object({
  epoch: z.number(),
  batch: z.number(),
  message: z.string(),
  severity: z.number(),
  target_paths: z.array(z.string()),
  by_field: z.record(z.string()),
  applied_diff: z.string(),
  timestamp: z.number().optional(),
});
export type GradientEntry = z.infer<typeof GradientEntry>;

export const SweepCell = z.object({
  cell_index: z.number(),
  parameters: z.record(z.unknown()),
  score: z.number().nullable(),
});
export type SweepCell = z.infer<typeof SweepCell>;

export const SweepAxis = z.object({
  name: z.string(),
  values: z.array(z.unknown()),
});
export type SweepAxis = z.infer<typeof SweepAxis>;

export const SweepSnapshot = z.object({
  cells: z.array(SweepCell),
  axes: z.array(SweepAxis),
  score_range: z.tuple([z.number(), z.number()]).nullable(),
  best_cell_index: z.number().nullable(),
  total_cells: z.number(),
  finished: z.boolean(),
});
export type SweepSnapshot = z.infer<typeof SweepSnapshot>;

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

// --- Benchmark shapes --------------------------------------------------------

export const BenchmarkTokens = z.object({
  prompt: z.number(),
  completion: z.number(),
});
export type BenchmarkTokens = z.infer<typeof BenchmarkTokens>;

export const BenchmarkCell = z.object({
  task: z.string(),
  method: z.string(),
  seed: z.number(),
  metric: z.string(),
  score: z.number(),
  tokens: BenchmarkTokens,
  latency_s: z.number(),
});
export type BenchmarkCell = z.infer<typeof BenchmarkCell>;

export const BenchmarkSummaryRow = z.object({
  task: z.string(),
  method: z.string(),
  mean: z.number(),
  std: z.number(),
  tokens_mean: z.number(),
  latency_mean: z.number(),
  n: z.number(),
});
export type BenchmarkSummaryRow = z.infer<typeof BenchmarkSummaryRow>;

export const BenchmarkReport = z.object({
  cells: z.array(BenchmarkCell),
  summary: z.array(BenchmarkSummaryRow),
  headline_findings: z.record(z.string()),
});
export type BenchmarkReport = z.infer<typeof BenchmarkReport>;

export const BenchmarkLeaderboardEntry = z.object({
  task: z.string(),
  method: z.string(),
  mean: z.number(),
});
export type BenchmarkLeaderboardEntry = z.infer<typeof BenchmarkLeaderboardEntry>;

export const BenchmarkListItem = z.object({
  id: z.string(),
  name: z.string(),
  created_at: z.number(),
  tag: z.string().nullable(),
  tagged_at: z.number().nullable(),
  n_tasks: z.number(),
  n_methods: z.number(),
  summary: z.string(),
  leaderboard: z.array(BenchmarkLeaderboardEntry),
});
export type BenchmarkListItem = z.infer<typeof BenchmarkListItem>;

export const BenchmarkBaseline = z.object({
  id: z.string(),
  name: z.string(),
  tag: z.string().nullable(),
  created_at: z.number(),
});
export type BenchmarkBaseline = z.infer<typeof BenchmarkBaseline>;

export const BenchmarkDeltaRow = z.object({
  task: z.string(),
  method: z.string(),
  delta: z.number(),
});
export type BenchmarkDeltaRow = z.infer<typeof BenchmarkDeltaRow>;

export const BenchmarkDetailResponse = z.object({
  id: z.string(),
  name: z.string(),
  created_at: z.number(),
  tag: z.string().nullable(),
  tagged_at: z.number().nullable(),
  n_tasks: z.number(),
  n_methods: z.number(),
  report: BenchmarkReport,
  baseline: BenchmarkBaseline.nullable(),
  delta: z.array(BenchmarkDeltaRow),
});
export type BenchmarkDetailResponse = z.infer<typeof BenchmarkDetailResponse>;

export const BenchmarkIngestResponse = z.object({ id: z.string() });
export type BenchmarkIngestResponse = z.infer<typeof BenchmarkIngestResponse>;

export const BenchmarkOkResponse = z.object({ ok: z.boolean() });
export type BenchmarkOkResponse = z.infer<typeof BenchmarkOkResponse>;

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

export const IterationsResponse = z.object({
  iterations: z
    .array(
      z.object({
        iter_index: z.number(),
        phase: z.string().nullable().default(null),
        score: z.number().nullable().default(null),
        text: z.string().nullable().default(null),
        metadata: z.record(z.unknown()).default({}),
      }),
    )
    .default([]),
  max_iter: z.number().nullable().default(null),
  threshold: z.number().nullable().default(null),
  converged: z.boolean().nullable().default(null),
});
export type IterationsResponse = z.infer<typeof IterationsResponse>;

export const GraphResponse = z.object({ mermaid: z.string() });
export type GraphResponse = z.infer<typeof GraphResponse>;

const IoField = z.object({
  name: z.string(),
  type: z.string().default("unknown"),
  description: z.string().default(""),
  system: z.boolean().default(false),
});
export type IoField = z.infer<typeof IoField>;

export const IoTypeNode = z.object({
  key: z.string(),
  name: z.string(),
  fields: z.array(IoField).default([]),
});
export type IoTypeNode = z.infer<typeof IoTypeNode>;

export const IoAgentEdge = z.object({
  agent_path: z.string(),
  class_name: z.string().default("Agent"),
  kind: z.string().default("leaf"),
  from: z.string(),
  to: z.string(),
  composite_path: z.string().nullable().optional().default(null),
});
export type IoAgentEdge = z.infer<typeof IoAgentEdge>;

export const IoGraphResponse = z.object({
  root: z.string().nullable().default(null),
  nodes: z.array(IoTypeNode).default([]),
  edges: z.array(IoAgentEdge).default([]),
});
export type IoGraphResponse = z.infer<typeof IoGraphResponse>;

export const AgentInvocation = z.object({
  id: z.string(),
  started_at: z.number(),
  finished_at: z.number().nullable().default(null),
  latency_ms: z.number().nullable().default(null),
  prompt_tokens: z.number().default(0),
  completion_tokens: z.number().default(0),
  hash_prompt: z.string().nullable().default(null),
  hash_input: z.string().nullable().default(null),
  hash_content: z.string().nullable().default(null),
  status: z.enum(["ok", "error"]),
  error: z.string().nullable().default(null),
  langfuse_url: z.string().nullable().default(null),
  script: z.string().nullable().default(null),
});
export type AgentInvocation = z.infer<typeof AgentInvocation>;

export const AgentInvocationsResponse = z.object({
  agent_path: z.string(),
  invocations: z.array(AgentInvocation).default([]),
});
export type AgentInvocationsResponse = z.infer<typeof AgentInvocationsResponse>;

export const AgentMetaResponse = z.object({
  agent_path: z.string(),
  class_name: z.string().nullable().default(null),
  kind: z.string().nullable().default(null),
  hash_content: z.string().nullable().default(null),
  role: z.string().nullable().default(null),
  task: z.string().nullable().default(null),
  rules: z.array(z.string()).default([]),
  examples: z.array(z.record(z.unknown())).default([]),
  config: z.record(z.unknown()).nullable().default(null),
  input_schema: IoTypeNode.nullable().default(null),
  output_schema: IoTypeNode.nullable().default(null),
  forward_in_overridden: z.boolean().default(false),
  forward_out_overridden: z.boolean().default(false),
  trainable_paths: z.array(z.string()).default([]),
  langfuse_search_url: z.string().nullable().default(null),
});
export type AgentMetaResponse = z.infer<typeof AgentMetaResponse>;

export const AgentPromptsResponse = z.object({
  agent_path: z.string(),
  renderer: z.string().default("xml"),
  entries: z
    .array(
      z.object({
        invocation_id: z.string(),
        started_at: z.number(),
        hash_prompt: z.string().nullable().default(null),
        system: z.string().nullable().default(null),
        user: z.string().nullable().default(null),
        replayed: z.boolean().default(false),
      }),
    )
    .default([]),
});
export type AgentPromptsResponse = z.infer<typeof AgentPromptsResponse>;

export const AgentValuesResponse = z.object({
  agent_path: z.string(),
  attribute: z.string(),
  side: z.enum(["in", "out"]),
  type: z.string(),
  values: z
    .array(
      z.object({
        invocation_id: z.string(),
        started_at: z.number(),
        value: z.unknown(),
      }),
    )
    .default([]),
});
export type AgentValuesResponse = z.infer<typeof AgentValuesResponse>;

export const AgentEventsResponse = z.object({
  run_id: z.string(),
  events: z.array(Envelope),
});
export type AgentEventsResponse = z.infer<typeof AgentEventsResponse>;

export const RunEventsResponse = z.object({
  run_id: z.string(),
  events: z.array(Envelope),
});
export type RunEventsResponse = z.infer<typeof RunEventsResponse>;

export const ArchivedRunRecord = z.object({
  summary: RunSummary,
  events: z.array(Envelope),
});
export type ArchivedRunRecord = z.infer<typeof ArchivedRunRecord>;

export const StatsResponse = GlobalStats.extend({
  cost_totals: z.record(CostTotals).default({}),
});
export type StatsResponse = z.infer<typeof StatsResponse>;

export const EvolutionResponse = z.object({
  generations: z.array(Generation.extend({ run_id: z.string(), algorithm_path: stringOrNull })),
});
export type EvolutionResponse = z.infer<typeof EvolutionResponse>;

// --- Cassettes ---------------------------------------------------------------

export const CassetteMetadata = z
  .object({
    algorithm: z.string().optional(),
    run_id: z.string().optional(),
    recorded_at: z.number().optional(),
    epoch: z.number().optional(),
    step_idx: z.number().optional(),
  })
  .passthrough();
export type CassetteMetadata = z.infer<typeof CassetteMetadata>;

export const CassetteSummary = z.object({
  path: z.string(),
  type: z.enum(["trace", "inference", "training", "unknown"]),
  size: z.number(),
  mtime: z.number(),
  metadata: CassetteMetadata.default({}),
});
export type CassetteSummary = z.infer<typeof CassetteSummary>;

export const CassetteReplayResponse = z.object({
  run_id: z.string(),
  emitted: z.number().optional(),
});
export type CassetteReplayResponse = z.infer<typeof CassetteReplayResponse>;

export const CassetteDiffEntry = z.object({
  event_index: z.number(),
  field: z.string(),
  expected: z.unknown(),
  actual: z.unknown(),
});
export type CassetteDiffEntry = z.infer<typeof CassetteDiffEntry>;

export const CassetteDeterminismResponse = z.object({
  ok: z.boolean(),
  diff: z.array(CassetteDiffEntry),
});
export type CassetteDeterminismResponse = z.infer<typeof CassetteDeterminismResponse>;

export const CassettePreviewResponse = z.object({
  path: z.string(),
  events: z.array(Envelope),
});
export type CassettePreviewResponse = z.infer<typeof CassettePreviewResponse>;

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
