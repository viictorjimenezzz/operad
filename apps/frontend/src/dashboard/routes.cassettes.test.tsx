import { dashboardRoutes } from "@/dashboard/routes";
import { matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

describe("dashboard cassette routes", () => {
  it("matches /cassettes index route", () => {
    const matches = matchRoutes(dashboardRoutes, "/cassettes");
    expect(matches).toBeTruthy();
    expect(matches?.at(-1)?.route.path).toBe("cassettes");
  });

  it("matches /cassettes/* detail route", () => {
    const matches = matchRoutes(dashboardRoutes, "/cassettes/nested/trace.jsonl");
    expect(matches).toBeTruthy();
    expect(matches?.at(-1)?.route.path).toBe("cassettes/*");
  });
});
