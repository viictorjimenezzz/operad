import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LangfuseLink } from "@/shared/panels/langfuse-link";
import { langfuseUrlFor } from "@/lib/langfuse";

const mockUseManifest = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useManifest: () => mockUseManifest(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("langfuseUrlFor", () => {
  it("constructs a trace URL", () => {
    expect(langfuseUrlFor("http://lf.example", "run-1")).toBe(
      "http://lf.example/trace/run-1",
    );
  });

  it("strips trailing slash from base", () => {
    expect(langfuseUrlFor("http://lf.example/", "run-1")).toBe(
      "http://lf.example/trace/run-1",
    );
  });

  it("appends spanId as observation param", () => {
    expect(langfuseUrlFor("http://lf.example", "run-1", "span-abc")).toBe(
      "http://lf.example/trace/run-1?observation=span-abc",
    );
  });
});

describe("<LangfuseLink />", () => {
  it("renders button when langfuseUrl and runId are set", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<LangfuseLink runId="run-1" />);
    expect(screen.getByText("view in langfuse →")).toBeDefined();
  });

  it("renders nothing when langfuseUrl is null", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: null } });
    const { container } = render(<LangfuseLink runId="run-1" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when runId is null", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    const { container } = render(<LangfuseLink runId={null} />);
    expect(container.firstChild).toBeNull();
  });
});
