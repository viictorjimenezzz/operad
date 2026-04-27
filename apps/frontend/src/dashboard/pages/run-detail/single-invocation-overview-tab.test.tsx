import { NotesSection } from "@/components/agent-view/overview/notes-section";
import { RunStatusStrip } from "@/components/agent-view/overview/run-status-strip";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  usePatchRunNotes: () => ({ mutateAsync }),
}));

const summary = {
  run_id: "run-1",
  started_at: 1,
  last_event_at: 2,
  state: "ended",
  has_graph: true,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "Root",
  script: null,
  event_counts: {},
  event_total: 2,
  duration_ms: 1420,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 312,
  completion_tokens: 198,
  cost: { prompt_tokens: 312, completion_tokens: 198, cost_usd: 0.0042 },
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
  notes_markdown: "",
};

describe("single invocation overview pieces", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  it("renders the slim status strip before the page body", () => {
    render(
      <MemoryRouter>
        <RunStatusStrip
          dataSummary={summary}
          dataInvocations={{
            agent_path: "Root",
            invocations: [
              {
                id: "Root:0",
                started_at: 1,
                status: "ok",
                latency_ms: 1420,
                prompt_tokens: 312,
                completion_tokens: 198,
                cost_usd: 0.0042,
                hash_content: "abc123",
              },
            ],
          }}
          runId="run-1"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("ok")).toBeTruthy();
    expect(screen.getByText("1.4s")).toBeTruthy();
    expect(screen.getByText("510")).toBeTruthy();
    expect(screen.getByText("$0.0042")).toBeTruthy();
  });

  it("saves notes inline and shows the returned markdown", async () => {
    mutateAsync.mockResolvedValue({
      run_id: "run-1",
      notes_markdown: "**reviewed**",
      updated_at: 2,
    });

    render(<NotesSection dataSummary={summary} runId="run-1" />);

    fireEvent.click(screen.getByLabelText("edit markdown"));
    fireEvent.change(screen.getByLabelText("markdown text"), {
      target: { value: "**reviewed**" },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        runId: "run-1",
        markdown: "**reviewed**",
      }),
    );
    expect(await screen.findByText("reviewed")).toBeTruthy();
  });
});
