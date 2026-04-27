import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SynthesisCard } from "./synthesis-card";

afterEach(cleanup);

describe("<SynthesisCard />", () => {
  it("renders markdown answer and synthesizer link", () => {
    render(<SynthesisCard answer="**Final** answer" childHref="/agents/h/runs/r1" />);

    expect(screen.getByText("Synthesized answer")).toBeDefined();
    expect(screen.getByText("Final")).toBeDefined();
    expect(screen.getByRole("link", { name: /open synthesizer run/i }).getAttribute("href")).toBe(
      "/agents/h/runs/r1",
    );
  });

  it("shows an empty state when the answer is missing", () => {
    render(<SynthesisCard answer={null} childHref={null} />);

    expect(screen.getByText("synthesis not available")).toBeDefined();
  });
});
