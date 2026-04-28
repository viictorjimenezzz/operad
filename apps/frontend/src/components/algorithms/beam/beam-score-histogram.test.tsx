import { BeamScoreHistogramTab } from "@/components/algorithms/beam/score-histogram-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("BeamScoreHistogramTab", () => {
  it("renders histogram bins with a k-cutoff marker", () => {
    render(
      <MemoryRouter>
        <BeamScoreHistogramTab
          data={[
            { candidate_index: 0, score: 0.2, text: "a", timestamp: 1, iter_index: 0 },
            { candidate_index: 1, score: 0.9, text: "b", timestamp: 1, iter_index: 0 },
          ]}
          dataIterations={{ iterations: [{ metadata: { top_indices: [1] } }] }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("10 bins")).toBeTruthy();
    expect(screen.getByText(/K cutoff/)).toBeTruthy();
  });

  it("renders a scored-empty state when all candidate scores are null", () => {
    render(
      <MemoryRouter>
        <BeamScoreHistogramTab
          data={[{ candidate_index: 0, score: null, text: "short", timestamp: 1, iter_index: 0 }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("no scored candidates")).toBeTruthy();
  });
});
