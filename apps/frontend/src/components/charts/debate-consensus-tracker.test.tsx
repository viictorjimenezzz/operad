import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DebateConsensusTracker } from "./debate-consensus-tracker";

afterEach(cleanup);

const twoRounds = [
  {
    round_index: 0,
    proposals: [],
    critiques: [],
    scores: [0.8, 0.3],
    timestamp: 1.0,
  },
  {
    round_index: 1,
    proposals: [],
    critiques: [],
    scores: [0.9, 0.85],
    timestamp: 2.0,
  },
];

describe("<DebateConsensusTracker />", () => {
  it("shows empty state for null data", () => {
    render(<DebateConsensusTracker data={null} />);
    expect(screen.getByText("not enough rounds")).toBeDefined();
  });

  it("shows empty state for a single round", () => {
    render(<DebateConsensusTracker data={[twoRounds[0]]} />);
    expect(screen.getByText("not enough rounds")).toBeDefined();
  });

  it("shows empty state for empty array", () => {
    render(<DebateConsensusTracker data={[]} />);
    expect(screen.getByText("not enough rounds")).toBeDefined();
  });

  it("renders without throwing for two or more rounds", () => {
    // recharts does not render SVG in happy-dom; just verify no error is thrown
    const { container } = render(<DebateConsensusTracker data={twoRounds} />);
    expect(container.firstChild).not.toBeNull();
  });
});
