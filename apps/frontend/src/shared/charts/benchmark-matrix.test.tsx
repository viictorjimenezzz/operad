import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BenchmarkMatrix } from "./benchmark-matrix";

describe("BenchmarkMatrix", () => {
  it("renders mean±std cells and delta values", () => {
    render(
      <BenchmarkMatrix
        summary={[
          {
            task: "classification",
            method: "tgd",
            mean: 0.8123,
            std: 0.031,
            tokens_mean: 100,
            latency_mean: 1.2,
            n: 3,
          },
          {
            task: "classification",
            method: "momentum",
            mean: 0.702,
            std: 0.012,
            tokens_mean: 110,
            latency_mean: 1.3,
            n: 3,
          },
        ]}
        delta={[
          { task: "classification", method: "tgd", delta: 0.03 },
          { task: "classification", method: "momentum", delta: -0.01 },
        ]}
      />,
    );

    expect(screen.getByText("0.812±0.031")).toBeTruthy();
    expect(screen.getByText("0.702±0.012")).toBeTruthy();
    expect(screen.getByText("Δ +0.030")).toBeTruthy();
    expect(screen.getByText("Δ -0.010")).toBeTruthy();
  });
});
