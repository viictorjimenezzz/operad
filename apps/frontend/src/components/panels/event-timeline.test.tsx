import { EventTimeline } from "@/components/panels/event-timeline";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseManifest = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useManifest: () => mockUseManifest(),
}));

const baseEvent = {
  type: "agent_event",
  run_id: "run-1",
  agent_path: "RootAgent",
  kind: "start",
  input: null,
  output: null,
  started_at: 1.23,
  finished_at: null,
  metadata: {},
  error: null,
} as const;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("<EventTimeline /> langfuse links", () => {
  it("renders event link when metadata has span_id", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<EventTimeline data={[{ ...baseEvent, metadata: { span_id: "span-a" } }]} />);

    const link = screen.getByLabelText("Open event in Langfuse");
    expect(link.getAttribute("href")).toBe("http://lf.example/trace/run-1?observation=span-a");
  });

  it("falls back to spanId then observation_id", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    const events = [
      { ...baseEvent, started_at: 1.24, metadata: { spanId: "span-b" } },
      { ...baseEvent, started_at: 1.25, metadata: { observation_id: "span-c" } },
    ];

    render(<EventTimeline data={events} />);

    const links = screen.getAllByLabelText("Open event in Langfuse");
    expect(links).toHaveLength(2);
    expect(links[0]?.getAttribute("href")).toBe("http://lf.example/trace/run-1?observation=span-b");
    expect(links[1]?.getAttribute("href")).toBe("http://lf.example/trace/run-1?observation=span-c");
  });

  it("renders no event link when span metadata is absent", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: "http://lf.example" } });
    render(<EventTimeline data={[baseEvent]} />);

    expect(screen.queryByLabelText("Open event in Langfuse")).toBeNull();
  });

  it("renders no event link when langfuseUrl is null", () => {
    mockUseManifest.mockReturnValue({ data: { langfuseUrl: null } });
    render(<EventTimeline data={[{ ...baseEvent, metadata: { span_id: "span-a" } }]} />);

    expect(screen.queryByLabelText("Open event in Langfuse")).toBeNull();
  });
});
