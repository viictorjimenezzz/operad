import { ParseError, dashboardApi } from "@/lib/api/dashboard";
import { afterEach, describe, expect, it, vi } from "vitest";

function mockJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("dashboardApi cassette endpoints", () => {
  it("parses cassette list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse([
          {
            path: "trace.jsonl",
            type: "trace",
            size: 12,
            mtime: 1000,
            metadata: { run_id: "r1" },
          },
        ]),
      ),
    );

    const rows = await dashboardApi.cassettes();
    expect(rows).toHaveLength(1);
    expect(rows[0]?.path).toBe("trace.jsonl");
  });

  it("posts replay and returns run id", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockJsonResponse({ run_id: "cassette-1", emitted: 2 }));
    vi.stubGlobal("fetch", fetchMock);

    const out = await dashboardApi.cassetteReplay({ path: "trace.jsonl", delayMs: 0 });
    expect(out.run_id).toBe("cassette-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/cassettes/replay?delay_ms=0",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("parses determinism response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          ok: false,
          diff: [{ event_index: 1, field: "payload.x", expected: 1, actual: 2 }],
        }),
      ),
    );

    const out = await dashboardApi.cassetteDeterminism("trace.jsonl");
    expect(out.ok).toBe(false);
    expect(out.diff[0]?.field).toBe("payload.x");
  });

  it("throws ParseError on malformed cassette schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse([
          {
            path: "trace.jsonl",
            type: "not-a-type",
            size: 12,
            mtime: 1000,
            metadata: {},
          },
        ]),
      ),
    );

    await expect(dashboardApi.cassettes()).rejects.toBeInstanceOf(ParseError);
  });
});
