import { BackendBadges } from "@/components/agent-view/insights/backend-badges";
import type { AgentMetaResponse, RunInvocation } from "@/lib/types";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

const invocation: RunInvocation = {
  id: "i1",
  started_at: 100,
  finished_at: 101,
  latency_ms: 1200,
  prompt_tokens: 12,
  completion_tokens: 7,
  cost_usd: 0.01,
  hash_model: "m",
  hash_prompt: "p",
  hash_graph: "g",
  hash_input: "i",
  hash_output_schema: "o",
  hash_config: "c",
  hash_content: "k",
  status: "ok",
  error: null,
  langfuse_url: null,
  script: null,
  backend: "llamacpp",
  model: "local-model",
  renderer: "xml",
};

const meta: AgentMetaResponse = {
  agent_path: "Root.reasoner",
  class_name: "Reasoner",
  kind: "leaf",
  hash_content: "hash-content",
  role: "role",
  task: "task",
  rules: [],
  examples: [],
  config: {
    backend: "openai",
    model: "gpt-4o-mini",
    sampling: { temperature: 0.7, top_p: 1.0 },
    resilience: {},
    io: { structured: true },
    runtime: { renderer: "xml", extra: { cache: true } },
  },
  input_schema: {},
  output_schema: {},
  forward_in_overridden: false,
  forward_out_overridden: false,
  trainable_paths: [],
  langfuse_search_url: null,
};

describe("BackendBadges", () => {
  it("renders backend/model/sampling badges", () => {
    render(<BackendBadges invocations={[invocation]} summaryRaw={{ synthetic: true }} meta={meta} />);
    expect(screen.getByText("openai")).toBeTruthy();
    expect(screen.getByText("gpt-4o-mini")).toBeTruthy();
    expect(screen.getByText("T 0.7")).toBeTruthy();
    expect(screen.getByText("top_p 1")).toBeTruthy();
    expect(screen.getByText("structured")).toBeTruthy();
    expect(screen.getByText(/cassette replay/i)).toBeTruthy();
  });
});
