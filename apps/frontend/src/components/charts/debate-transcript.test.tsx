import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DebateTranscript } from "./debate-transcript";

afterEach(cleanup);

const oneRound = [
  {
    round_index: 0,
    proposals: [
      { content: "My argument for A", author: "alice" },
      { content: "My argument for B", author: "bob" },
    ],
    critiques: [
      { target_author: "alice", comments: "Strong reasoning.", score: 0.8 },
      { target_author: "bob", comments: "Lacks evidence.", score: 0.3 },
    ],
    scores: [0.8, 0.3],
    timestamp: 1.0,
  },
];

const twoRounds = [
  ...oneRound,
  {
    round_index: 1,
    proposals: [
      { content: "Refined argument A", author: "alice" },
      { content: "Refined argument B", author: "bob" },
    ],
    critiques: [
      { target_author: "alice", comments: "Even better.", score: 0.9 },
      { target_author: "bob", comments: "Improved.", score: 0.6 },
    ],
    scores: [0.9, 0.6],
    timestamp: 2.0,
  },
];

describe("<DebateTranscript />", () => {
  it("shows empty state for null data", () => {
    render(<DebateTranscript data={null} />);
    expect(screen.getByText("no transcript yet")).toBeDefined();
  });

  it("shows empty state for empty array", () => {
    render(<DebateTranscript data={[]} />);
    expect(screen.getByText("no transcript yet")).toBeDefined();
  });

  it("renders round header with winner badge", () => {
    render(<DebateTranscript data={oneRound} />);
    expect(screen.getByText(/round 1/i)).toBeDefined();
    expect(screen.getByText(/winner: alice/i)).toBeDefined();
  });

  it("first round is expanded by default — shows proposal text", () => {
    render(<DebateTranscript data={oneRound} />);
    expect(screen.getByText("My argument for A")).toBeDefined();
    expect(screen.getByText("My argument for B")).toBeDefined();
  });

  it("clicking a round header collapses it", () => {
    render(<DebateTranscript data={oneRound} />);
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(screen.queryByText("My argument for A")).toBeNull();
  });

  it("renders multiple rounds", () => {
    render(<DebateTranscript data={twoRounds} />);
    expect(screen.getByText(/round 1/i)).toBeDefined();
    expect(screen.getByText(/round 2/i)).toBeDefined();
  });

  it("deduplicates repeated streamed rounds by round_index", () => {
    render(<DebateTranscript data={[...twoRounds, oneRound[0]!]} />);
    expect(screen.getAllByText(/round 1/i)).toHaveLength(1);
  });

  it("renders gracefully with missing proposals", () => {
    const sparse = [{ round_index: 0, proposals: [], critiques: [], scores: [], timestamp: null }];
    render(<DebateTranscript data={sparse} />);
    expect(screen.getByText(/round 1/i)).toBeDefined();
  });
});
