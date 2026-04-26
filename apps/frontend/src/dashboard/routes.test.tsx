import { describe, expect, it } from "vitest";

import { dashboardRouter } from "./routes";

describe("dashboardRouter", () => {
  it("registers nested run-detail tabs", () => {
    const root = dashboardRouter.routes[0];
    if (!root || !("children" in root) || !root.children) {
      throw new Error("missing root children");
    }
    const runDetail = root.children.find((c) => c.path === "runs/:runId");
    expect(runDetail).toBeDefined();
    if (!runDetail || !("children" in runDetail) || !runDetail.children) {
      throw new Error("missing run-detail children");
    }
    const tabs = runDetail.children.map((c) => c.path ?? (c.index ? "(index)" : ""));
    expect(tabs).toContain("(index)");
    expect(tabs).toContain("graph");
    expect(tabs).toContain("invocations");
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
