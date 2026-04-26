import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { BeamCandidateChart } from "./beam-candidate-chart";

afterEach(cleanup);

describe("BeamCandidateChart", () => {
  it("renders empty state for missing candidates", () => {
    render(<BeamCandidateChart data={[]} />);
    expect(screen.getByText("no beam candidates")).toBeTruthy();
  });

  it("renders top-k text compare and pruning metadata", () => {
    render(
      <BeamCandidateChart
        data={[
          { candidate_index: 0, score: 0.2, text: "c0", timestamp: 1, iter_index: 0 },
          { candidate_index: 1, score: 0.8, text: "c1", timestamp: 1, iter_index: 0 },
          { candidate_index: 2, score: 0.9, text: "c2", timestamp: 1, iter_index: 0 },
        ]}
        iterationsData={{
          iterations: [
            {
              iter_index: 0,
              phase: "prune",
              metadata: { top_indices: [2, 1], dropped_indices: [0] },
            },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByText("candidate 2"));
    fireEvent.click(screen.getByText("candidate 1"));

    expect(screen.getByText("c2")).toBeTruthy();
    expect(screen.getByText("c1")).toBeTruthy();
    expect(screen.getByText(/kept \[2, 1\]/)).toBeTruthy();
    expect(screen.getByText(/dropped \[0\]/)).toBeTruthy();
  });

  it("caps top-k compare selection to three", () => {
    render(
      <BeamCandidateChart
        data={[
          { candidate_index: 0, score: 0.1, text: "c0", timestamp: 1, iter_index: 0 },
          { candidate_index: 1, score: 0.2, text: "c1", timestamp: 1, iter_index: 0 },
          { candidate_index: 2, score: 0.3, text: "c2", timestamp: 1, iter_index: 0 },
          { candidate_index: 3, score: 0.4, text: "c3", timestamp: 1, iter_index: 0 },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("candidate 0"));
    fireEvent.click(screen.getByText("candidate 1"));
    fireEvent.click(screen.getByText("candidate 2"));
    fireEvent.click(screen.getByText("candidate 3"));

    const checked = [...document.querySelectorAll('input[type="checkbox"]')].filter(
      (n) => (n as HTMLInputElement).checked,
    );
    expect(checked).toHaveLength(3);
  });
});
