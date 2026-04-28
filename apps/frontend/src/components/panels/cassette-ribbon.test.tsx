import { CassetteRibbon } from "@/components/panels/cassette-ribbon";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

describe("<CassetteRibbon />", () => {
  it("renders cassette mode with path and stale indicator", () => {
    mockUseManifest.mockReturnValue({
      isLoading: false,
      data: {
        cassetteMode: true,
        cassettePath: "/tmp/cassette.jsonl",
        cassetteStale: true,
        tracePath: null,
      },
    });

    render(<CassetteRibbon />);
    expect(screen.getByText("cassette: enabled")).toBeDefined();
    expect(screen.getByText("/tmp/cassette.jsonl")).toBeDefined();
    expect(screen.getByText("stale")).toBeDefined();
  });

  it("renders trace path when trace is enabled", () => {
    mockUseManifest.mockReturnValue({
      isLoading: false,
      data: {
        cassetteMode: false,
        cassettePath: null,
        cassetteStale: false,
        tracePath: "/tmp/operad-trace.jsonl",
      },
    });

    render(<CassetteRibbon />);
    expect(screen.getByText("trace:")).toBeDefined();
    expect(screen.getByText("/tmp/operad-trace.jsonl")).toBeDefined();
  });

  it("renders both cassette and trace when both are present", () => {
    mockUseManifest.mockReturnValue({
      isLoading: false,
      data: {
        cassetteMode: true,
        cassettePath: "/tmp/cassette.jsonl",
        cassetteStale: false,
        tracePath: "/tmp/operad-trace.jsonl",
      },
    });

    render(<CassetteRibbon />);
    expect(screen.getByText("cassette: enabled")).toBeDefined();
    expect(screen.getByText("trace:")).toBeDefined();
  });

  it("renders nothing when cassette and trace are both absent", () => {
    mockUseManifest.mockReturnValue({
      isLoading: false,
      data: {
        cassetteMode: false,
        cassettePath: null,
        cassetteStale: false,
        tracePath: null,
      },
    });

    const { container } = render(<CassetteRibbon />);
    expect(container.firstChild).toBeNull();
  });
});
