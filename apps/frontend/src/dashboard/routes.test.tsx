import { describe, expect, it } from "vitest";

import { dashboardRouter } from "./routes";

describe("dashboardRouter", () => {
  it("registers the agent run-detail route shape", () => {
    const root = dashboardRouter.routes[0];
    if (!root || !("children" in root) || !root.children) {
      throw new Error("missing root children");
    }
    const runDetail = root.children.find((c) => c.path === "agents/:hashContent/runs/:runId");
    expect(runDetail).toBeDefined();
    if (!runDetail || !("children" in runDetail) || !runDetail.children) {
      throw new Error("missing run-detail children");
    }
    const tabs = runDetail.children.map((c) => c.path ?? (c.index ? "(index)" : ""));
    expect(tabs).toContain("(index)");
    expect(tabs).toContain("graph");
    expect(tabs).toContain("metrics");
    expect(tabs).toContain("drift");
    expect(tabs).not.toContain("invocations");
    expect(tabs).not.toContain("cost");
    expect(tabs).not.toContain("train");
    const graph = runDetail.children.find((c) => c.path === "graph");
    expect(graph && "errorElement" in graph ? graph.errorElement : undefined).toBeDefined();
  });

  it("registers algorithm, training, and OPRO detail routes without the legacy /runs route", () => {
    const root = dashboardRouter.routes[0];
    if (!root || !("children" in root) || !root.children) {
      throw new Error("missing root children");
    }
    const paths = root.children.map((r) => r.path ?? "");
    expect(paths).toContain("algorithms/:runId");
    expect(paths).toContain("training/:runId");
    expect(paths).toContain("opro");
    expect(paths).toContain("opro/:runId");
    expect(paths).not.toContain("runs/:runId");
  });

  it("registers benchmark routes", () => {
    const root = dashboardRouter.routes[0];
    if (!root || !("children" in root) || !root.children) {
      throw new Error("missing root children");
    }
    const paths = root.children.map((r) => r.path ?? "");
    expect(paths).toContain("benchmarks");
    expect(paths).toContain("benchmarks/:benchmarkId");
  });
});
