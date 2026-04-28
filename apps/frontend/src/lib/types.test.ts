import {
  AgentEventEnvelope,
  AgentEventsResponse,
  AgentInvocationDiffResponse,
  AgentInvocationsResponse,
  AgentMetaResponse,
  AgentParametersResponse,
  AgentPromptsResponse,
  AgentValuesResponse,
  AlgoEventEnvelope,
  CostUpdateEnvelope,
  Envelope,
  FitnessEntry,
  IoGraphResponse,
  MutationsMatrix,
  ProgressSnapshot,
  RunInvocationsResponse,
  RunSummary,
  SlotOccupancyEnvelope,
  StatsUpdateEnvelope,
  SweepSnapshot,
} from "@/lib/types";
import { describe, expect, it } from "vitest";

describe("envelope schemas", () => {
  it("parses an agent_event with full metadata", () => {
    const raw = {
      type: "agent_event",
      run_id: "abcd",
      agent_path: "Pipeline.stage_0",
      kind: "end",
      input: { text: "hi" },
      output: { answer: "hello", prompt_tokens: 10, completion_tokens: 5 },
      started_at: 100,
      finished_at: 101,
      metadata: { is_root: true },
      error: null,
    };
    const parsed = AgentEventEnvelope.parse(raw);
    expect(parsed.kind).toBe("end");
    expect(parsed.metadata.is_root).toBe(true);
  });

  it("parses an algo_event generation", () => {
    const raw = {
      type: "algo_event",
      run_id: "x",
      algorithm_path: "EvoGradient",
      kind: "generation",
      payload: {
        gen_index: 0,
        population_scores: [0.1, 0.2, 0.3],
        survivor_indices: [2],
        op_attempt_counts: { mutate_role: 5 },
        op_success_counts: { mutate_role: 1 },
      },
      started_at: 0,
      finished_at: 1,
      metadata: {},
    };
    const parsed = AlgoEventEnvelope.parse(raw);
    expect(parsed.kind).toBe("generation");
    expect(parsed.payload.gen_index).toBe(0);
  });

  it("Envelope union discriminates on type", () => {
    const slot = SlotOccupancyEnvelope.parse({
      type: "slot_occupancy",
      snapshot: [{ backend: "openai", host: "api", concurrency_used: 2 }],
    });
    expect(slot.snapshot).toHaveLength(1);

    const cost = CostUpdateEnvelope.parse({
      type: "cost_update",
      totals: { abc: { prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.001 } },
    });
    expect(cost.totals.abc?.cost_usd).toBe(0.001);

    const stats = StatsUpdateEnvelope.parse({
      type: "stats_update",
      stats: { runs_total: 3, event_total: 50 },
    });
    expect(stats.stats.runs_total).toBe(3);

    expect(() => Envelope.parse({ type: "agent_event", run_id: "x" })).toThrow();
  });
});

describe("RunSummary", () => {
  it("parses a minimal /runs/{id}/summary", () => {
    const summary = RunSummary.parse({
      run_id: "x",
      started_at: 100,
      last_event_at: 101,
      state: "running",
      has_graph: false,
      is_algorithm: true,
      algorithm_path: "EvoGradient",
      algorithm_kinds: ["generation"],
      root_agent_path: null,
      event_counts: { generation: 4 },
      event_total: 4,
      duration_ms: 1000,
      generations: [],
      iterations: [],
      rounds: [],
      candidates: [],
      batches: [],
      prompt_tokens: 0,
      completion_tokens: 0,
      error: null,
      algorithm_terminal_score: null,
    });
    expect(summary.algorithm_path).toBe("EvoGradient");
    expect(summary.cost).toBeUndefined();
  });
});

describe("agent-view contracts", () => {
  it("parses run invocations payload", () => {
    const parsed = RunInvocationsResponse.parse({
      agent_path: "Root",
      invocations: [
        {
          id: "inv-1",
          started_at: 100,
          finished_at: 101,
          latency_ms: 1000,
          prompt_tokens: 20,
          completion_tokens: 10,
          hash_prompt: "a1b2",
          hash_input: "c3d4",
          hash_content: "z9y8",
          status: "ok",
        },
      ],
    });
    expect(parsed.invocations[0]?.id).toBe("inv-1");
  });

  it("fails when invocation id is missing", () => {
    expect(() =>
      RunInvocationsResponse.parse({
        agent_path: "Root",
        invocations: [{ started_at: 100, hash_prompt: "a1", hash_input: "b2", hash_content: "c3" }],
      }),
    ).toThrow();
  });

  it("parses agent meta payload", () => {
    const parsed = AgentMetaResponse.parse({
      agent_path: "Root.reasoner",
      class_name: "Reasoner",
      kind: "leaf",
      hash_content: "ffff",
      config: {
        backend: "openai",
        model: "gpt-4o-mini",
      },
      forward_in_doc: "input docs",
      forward_out_doc: null,
    });
    expect(parsed.class_name).toBe("Reasoner");
    expect(parsed.config?.backend).toBe("openai");
    expect(parsed.forward_in_doc).toBe("input docs");
  });

  it("parses agent parameters payload", () => {
    const parsed = AgentParametersResponse.parse({
      agent_path: "Root.reasoner",
      parameters: [
        {
          path: "role",
          type: "TextParameter",
          value: "You are terse.",
          requires_grad: true,
          grad: { message: "be stricter", severity: 0.5, target_paths: ["role"], by_field: {} },
          constraint: { kind: "text", max_length: 300 },
        },
      ],
    });
    expect(parsed.parameters[0]?.path).toBe("role");
  });

  it("parses backend-style agent parameter rows", () => {
    const parsed = AgentParametersResponse.parse({
      agent_path: "VerifierAgent.generator",
      parameters: [
        {
          path: "role",
          value: "You are careful.",
          requires_grad: true,
          hash: null,
          tape_link: null,
          gradient: null,
        },
      ],
    });

    expect(parsed.parameters[0]?.type).toBe("Parameter");
    expect(parsed.parameters[0]?.hash).toBeNull();
    expect(parsed.parameters[0]?.gradient).toBeNull();
  });

  it("parses invocation diff payload", () => {
    const parsed = AgentInvocationDiffResponse.parse({
      from_invocation: "Root:0",
      to_invocation: "Root:1",
      from_hash_content: "aaa",
      to_hash_content: "bbb",
      changes: [{ path: "Root", kind: "role", detail: "- old\\n+ new" }],
    });
    expect(parsed.changes[0]?.kind).toBe("role");
  });

  it("fails when required meta fields are missing", () => {
    expect(() => AgentMetaResponse.parse({ agent_path: "Root.reasoner" })).toThrow();
  });
});

describe("panel shapes", () => {
  it("parses fitness rows", () => {
    expect(
      FitnessEntry.parse({
        gen_index: 0,
        best: 0.9,
        mean: 0.5,
        worst: 0.1,
        population_scores: [0.1, 0.5, 0.9],
        timestamp: 0,
      }).best,
    ).toBe(0.9);
  });

  it("parses mutations matrix", () => {
    const m = MutationsMatrix.parse({
      gens: [0, 1],
      ops: ["a"],
      success: [[1, 2]],
      attempts: [[3, 4]],
    });
    expect(m.ops).toEqual(["a"]);
  });

  it("parses sweep snapshot with 2-d grid", () => {
    const snap = SweepSnapshot.parse({
      cells: [
        { cell_index: 0, parameters: { temperature: 0.5, max_tokens: 100 }, score: 0.7 },
        { cell_index: 1, parameters: { temperature: 0.5, max_tokens: 200 }, score: 0.8 },
        { cell_index: 2, parameters: { temperature: 1.0, max_tokens: 100 }, score: null },
      ],
      axes: [
        { name: "temperature", values: [0.5, 1.0] },
        { name: "max_tokens", values: [100, 200] },
      ],
      score_range: [0.7, 0.8],
      best_cell_index: 1,
      total_cells: 3,
      finished: false,
    });
    expect(snap.cells).toHaveLength(3);
    expect(snap.cells[2]?.score).toBeNull();
    expect(snap.axes[0]?.name).toBe("temperature");
    expect(snap.best_cell_index).toBe(1);
    expect(snap.score_range).toEqual([0.7, 0.8]);
  });

  it("parses sweep snapshot with null score_range", () => {
    const snap = SweepSnapshot.parse({
      cells: [],
      axes: [],
      score_range: null,
      best_cell_index: null,
      total_cells: 0,
      finished: false,
    });
    expect(snap.score_range).toBeNull();
    expect(snap.best_cell_index).toBeNull();
  });

  it("parses progress snapshot", () => {
    const p = ProgressSnapshot.parse({
      epoch: 1,
      epochs_total: 5,
      batch: 2,
      batches_total: null,
      elapsed_s: 1.5,
      rate_batches_per_s: 0,
      eta_s: null,
      finished: false,
    });
    expect(p.epochs_total).toBe(5);
  });
});

describe("agent-view shapes", () => {
  it("parses io_graph payload", () => {
    const parsed = IoGraphResponse.parse({
      root: "Pipeline",
      nodes: [{ key: "pkg.Question", name: "Question", fields: [] }],
      edges: [
        {
          agent_path: "Pipeline.stage_0",
          class_name: "Reasoner",
          kind: "leaf",
          from: "pkg.Question",
          to: "pkg.Answer",
          composite_path: null,
        },
      ],
    });
    expect(parsed.root).toBe("Pipeline");
    expect(parsed.edges[0]?.agent_path).toBe("Pipeline.stage_0");
  });

  it("parses agent invocations/meta/prompts/values/events payloads", () => {
    expect(
      AgentInvocationsResponse.parse({
        agent_path: "Pipeline",
        invocations: [
          {
            id: "Pipeline:0",
            started_at: 1,
            finished_at: 2,
            latency_ms: 1000,
            prompt_tokens: 10,
            completion_tokens: 5,
            hash_prompt: "abc",
            hash_input: "def",
            hash_content: "ghi",
            status: "ok",
            error: null,
            langfuse_url: null,
            script: null,
          },
        ],
      }).invocations,
    ).toHaveLength(1);

    expect(
      AgentMetaResponse.parse({
        agent_path: "Pipeline.stage_0",
        class_name: "Reasoner",
        kind: "leaf",
        hash_content: "hash",
        role: "role",
        task: "task",
        rules: [],
        examples: [],
        config: {},
        input_schema: {},
        output_schema: {},
        forward_in_overridden: false,
        forward_out_overridden: false,
        forward_in_doc: null,
        forward_out_doc: null,
        trainable_paths: [],
        langfuse_search_url: null,
      }).class_name,
    ).toBe("Reasoner");

    expect(
      AgentPromptsResponse.parse({
        agent_path: "Pipeline.stage_0",
        renderer: "xml",
        entries: [
          {
            invocation_id: "id",
            started_at: 1,
            hash_prompt: "h",
            system: "s",
            user: "u",
            replayed: true,
          },
        ],
      }).entries[0]?.replayed,
    ).toBe(true);

    expect(
      AgentValuesResponse.parse({
        agent_path: "Pipeline.stage_0",
        attribute: "text",
        side: "in",
        type: "str",
        values: [{ invocation_id: "id", started_at: 1, value: "hello" }],
      }).values[0]?.value,
    ).toBe("hello");

    expect(
      AgentEventsResponse.parse({
        run_id: "r1",
        events: [
          {
            type: "agent_event",
            run_id: "r1",
            agent_path: "Pipeline",
            kind: "start",
            input: null,
            output: null,
            started_at: 1,
            finished_at: null,
            metadata: {},
            error: null,
          },
        ],
      }).events,
    ).toHaveLength(1);
  });
});
