import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RoundCard } from "./round-card";

afterEach(cleanup);

const round = {
  round_index: 0,
  proposals: [
    { author: "Proposer A", content: "Alpha answer" },
    { author: "Proposer B", content: "Beta answer" },
    { author: "Proposer C", content: "Gamma answer" },
  ],
  critiques: [
    { target_author: "Proposer A", comments: "needs more detail", score: 0.61 },
    { target_author: "Proposer B", comments: "good but tangential", score: 0.74 },
    { target_author: "Proposer C", comments: "off-topic", score: 0.52 },
  ],
  scores: [0.61, 0.74, 0.52],
  timestamp: 1,
};

describe("<RoundCard />", () => {
  it("renders proposer proposals, critic scores, and critique excerpts", () => {
    render(<RoundCard round={round} roundNumber={1} expanded />);

    expect(screen.getByText("Round 1")).toBeDefined();
    expect(screen.getByText("Proposer A")).toBeDefined();
    expect(screen.getByText("Alpha answer")).toBeDefined();
    expect(screen.getByText("Critic score: 0.61")).toBeDefined();
    expect(screen.getByText("needs more detail")).toBeDefined();
  });
});
