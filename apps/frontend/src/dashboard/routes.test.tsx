import { describe, expect, it } from "vitest";

import { dashboardRouter } from "./routes";

describe("dashboardRouter", () => {
  it("includes archive routes", () => {
    const root = dashboardRouter.routes[0];
    const children = root.children ?? [];
    const paths = children.map((child) => child.path).filter(Boolean);
    expect(paths).toContain("archive");
    expect(paths).toContain("archive/:runId");
  });
});
