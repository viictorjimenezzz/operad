import { describe, expect, it } from "vitest";
import { langfuseLinkProps, langfuseUrlFor } from "./langfuse";

describe("langfuseUrlFor", () => {
  it("constructs a trace URL", () => {
    expect(langfuseUrlFor("http://lf.example", "run-1")).toBe("http://lf.example/trace/run-1");
  });

  it("strips trailing slash from base", () => {
    expect(langfuseUrlFor("http://lf.example/", "run-1")).toBe("http://lf.example/trace/run-1");
  });

  it("appends spanId as observation param", () => {
    expect(langfuseUrlFor("http://lf.example", "run-1", "span-abc")).toBe(
      "http://lf.example/trace/run-1?observation=span-abc",
    );
  });
});

describe("langfuseLinkProps", () => {
  it("returns null when base URL is missing", () => {
    expect(langfuseLinkProps(null, "run-1")).toBeNull();
  });

  it("returns external-link props for a run trace", () => {
    expect(langfuseLinkProps("http://lf.example", "run-1")).toEqual({
      href: "http://lf.example/trace/run-1",
      target: "_blank",
      rel: "noopener noreferrer",
      title: "Open trace in Langfuse",
    });
  });

  it("returns external-link props for a specific span", () => {
    expect(langfuseLinkProps("http://lf.example", "run-1", "span-abcdef1234")).toEqual({
      href: "http://lf.example/trace/run-1?observation=span-abcdef1234",
      target: "_blank",
      rel: "noopener noreferrer",
      title: "Open span span-abc in Langfuse",
    });
  });
});
