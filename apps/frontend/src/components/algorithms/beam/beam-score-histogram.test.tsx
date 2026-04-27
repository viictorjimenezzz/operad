import { BeamScoreHistogram } from "@/components/algorithms/beam/beam-score-histogram";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("BeamScoreHistogram", () => {
  it("renders score distribution with top-k threshold", () => {
    render(
      <MemoryRouter>
        <BeamScoreHistogram
          data={[
            { candidate_index: 0, score: 0.2, text: "a", timestamp: 1, iter_index: 0 },
            { candidate_index: 1, score: 0.9, text: "b", timestamp: 1, iter_index: 0 },
          ]}
          dataIterations={{ iterations: [{ metadata: { top_indices: [1] } }] }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("score distribution")).toBeTruthy();
    expect(screen.getByText(/top-k threshold/)).toBeTruthy();
  });

  it("switches to text length distribution when scores are null", () => {
    render(
      <MemoryRouter>
        <BeamScoreHistogram
          data={[{ candidate_index: 0, score: null, text: "short", timestamp: 1, iter_index: 0 }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("text length distribution")).toBeTruthy();
    expect(screen.getByText(/judge=None/)).toBeTruthy();
  });
});
