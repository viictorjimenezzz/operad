import { BeamLeaderboardTab } from "@/components/algorithms/beam/leaderboard-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("BeamLeaderboardTab", () => {
  it("shows all ranked candidates with adjacent diffs and langfuse fallback", () => {
    render(
      <MemoryRouter>
        <BeamLeaderboardTab
          runId="beam-1"
          data={[
            { candidate_index: 0, score: 0.2, text: "low", timestamp: 1, iter_index: 0 },
            { candidate_index: 1, score: 0.9, text: "high", timestamp: 1, iter_index: 0 },
          ]}
          dataIterations={{
            iterations: [{ iter_index: 0, phase: "prune", metadata: { top_indices: [1] } }],
          }}
          dataChildren={[]}
          dataAgentsSummary={{
            run_id: "beam-1",
            agents: [{ agent_path: "Critic", langfuse_url: "https://langfuse.test/trace/beam-1" }],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText("high").length).toBeGreaterThan(0);
    expect(screen.getByText("low")).toBeTruthy();
    expect(screen.queryByText(/K =/)).toBeNull();
    expect(screen.getByText("Diff preview")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "open" })[0]?.getAttribute("href")).toBe(
      "https://langfuse.test/trace/beam-1",
    );
  });

  it("shows an empty state when candidate data is missing", () => {
    render(
      <MemoryRouter>
        <BeamLeaderboardTab runId="beam-1" data={null} />
      </MemoryRouter>,
    );

    expect(screen.getByText("no candidates")).toBeTruthy();
  });
});
