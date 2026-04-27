import {
  PromptTracebackView,
  parseTraceback,
} from "@/components/algorithms/trainer/prompt-traceback-view";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

const ndjson = `${JSON.stringify({
  agent_path: "Reasoner.stage_2",
  depth: 1,
  is_leaf: true,
  input: { question: "why" },
  output: { answer: "because" },
  rendered_prompt: "answer the question",
  gradient: {
    message: "tighten the wording",
    severity: 0.84,
    target_paths: ["task"],
    by_field: { task: "be precise" },
  },
})}\n`;

describe("PromptTracebackView", () => {
  it("parses persisted NDJSON frames", () => {
    const frames = parseTraceback(ndjson);
    expect(frames).toHaveLength(1);
    expect(frames[0]?.agent_path).toBe("Reasoner.stage_2");
    expect(frames[0]?.gradient?.severity).toBe(0.84);
  });

  it("loads and renders collapsible traceback frames", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        text: async () => ndjson,
      })),
    );

    render(
      wrapper(
        <PromptTracebackView
          runId="trainer-1"
          dataSummary={{
            has_traceback: true,
            traceback_path: "/tmp/trainer-1/epoch_3_batch_12.ndjson",
          }}
        />,
      ),
    );

    expect(await screen.findByText("Frame 1")).toBeTruthy();
    expect(screen.getAllByText("Reasoner.stage_2").length).toBeGreaterThan(0);
    expect(screen.getByText("tighten the wording")).toBeTruthy();
  });
});
