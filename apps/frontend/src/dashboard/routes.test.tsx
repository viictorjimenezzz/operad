import { describe, expect, it } from "vitest";

import { dashboardRouter } from "./routes";

describe("dashboardRouter", () => {
  it("includes archive routes", () => {
    const root = dashboardRouter.routes[0];
    if (!root || !("children" in root) || !root.children) {
      throw new Error("missing root children");
    }
    const paths = root.children.map((child) => child.path).filter(Boolean);
    expect(paths).toContain("archive");
    expect(paths).toContain("archive/:runId");
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
