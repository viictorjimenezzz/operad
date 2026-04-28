import { BeamLeaderboardTab } from "@/components/algorithms/beam/leaderboard-tab";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("BeamLeaderboardTab", () => {
  it("shows top-k candidates by default and expands to all candidates", () => {
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
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("K = 1 of 2")).toBeTruthy();
    expect(screen.getByText("high")).toBeTruthy();
    expect(screen.queryByText("low")).toBeNull();

    fireEvent.click(screen.getByText("show all candidates"));
    expect(screen.getByText("low")).toBeTruthy();
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
