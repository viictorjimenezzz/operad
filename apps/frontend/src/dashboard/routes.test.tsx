import { describe, expect, it } from "vitest";

import { dashboardRouter } from "./routes";

describe("dashboardRouter", () => {
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
