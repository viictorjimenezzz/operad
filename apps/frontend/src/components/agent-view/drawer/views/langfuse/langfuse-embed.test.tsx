import { LangfuseEmbed, buildLangfuseHref } from "@/components/agent-view/drawer/views/langfuse/langfuse-embed";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseManifest = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useManifest: () => mockUseManifest(),
}));

describe("buildLangfuseHref", () => {
  it("prioritizes invocationId over agentPath", () => {
    expect(
      buildLangfuseHref("http://lf.example", {
        invocationId: "inv-9",
        agentPath: "Pipeline.stage_0",
      }).href,
    ).toBe("http://lf.example/trace/inv-9");
  });

  it("uses path search when invocationId is absent", () => {
    expect(buildLangfuseHref("http://lf.example", { agentPath: "Pipeline.stage_0" }).href).toBe(
      "http://lf.example/traces?search=Pipeline.stage_0",
    );
  });

  it("falls back to base url", () => {
    expect(buildLangfuseHref("http://lf.example/", {}).href).toBe("http://lf.example");
  });
});

describe("LangfuseEmbed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({}),
        text: async () => "",
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows setup empty state when langfuseUrl is missing", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: null } });
    render(<LangfuseEmbed runId="run-1" payload={{}} />);

    expect(screen.getByText("Langfuse is not configured")).toBeTruthy();
    const guide = screen.getByRole("link", { name: /observability setup guide/i });
    expect(guide.getAttribute("href")).toBe("/apps/README.md#self-hosted-observability-stack");
  });

  it("opens external link and refreshes iframe", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(<LangfuseEmbed runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />);

    const frame = screen.getByTitle("Langfuse");
    expect(frame.getAttribute("src")).toBe("http://lf.example/traces?search=Pipeline.stage_0");

    fireEvent.click(screen.getByRole("button", { name: /open in langfuse/i }));
    expect(openSpy).toHaveBeenCalledWith(
      "http://lf.example/traces?search=Pipeline.stage_0",
      "_blank",
      "noopener",
    );

    const refreshButton = screen.getByRole("button", { name: "Refresh Langfuse frame" });
    fireEvent.click(refreshButton);

    expect(screen.getByTitle("Langfuse").getAttribute("src")).toBe(
      "http://lf.example/traces?search=Pipeline.stage_0",
    );
  });
});
