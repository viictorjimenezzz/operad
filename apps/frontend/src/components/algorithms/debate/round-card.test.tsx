import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    render(<RoundCard round={round} roundNumber={1} proposerCount={3} />);

    expect(screen.getByText("Round 1")).toBeDefined();
    expect(screen.getByText("Proposer A")).toBeDefined();
    expect(screen.getByText("Alpha answer")).toBeDefined();
    expect(
      screen.getByRole("button", { name: "show critic reasoning for Proposer A" }),
    ).toBeDefined();
  });

  it("toggles a proposal cell between proposal text and critic reasoning", () => {
    render(<RoundCard round={round} roundNumber={1} proposerCount={3} />);

    fireEvent.click(screen.getByRole("button", { name: "show critic reasoning for Proposer A" }));

    expect(screen.getByText("needs more detail")).toBeDefined();
    expect(screen.queryByText("Alpha answer")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "show proposal for Proposer A" }));

    expect(screen.getByText("Alpha answer")).toBeDefined();
    expect(screen.queryByText("needs more detail")).toBeNull();
  });

  it("preserves empty columns for missing proposals", () => {
    render(
      <RoundCard
        round={{ ...round, proposals: round.proposals.slice(0, 2) }}
        roundNumber={1}
        proposerCount={3}
      />,
    );

    expect(screen.getByText("No proposal recorded.")).toBeDefined();
  });
});
