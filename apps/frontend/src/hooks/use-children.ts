import { RunSummary as RunSummarySchema } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
  metrics: z.record(z.unknown()).optional(),
  metadata: z.record(z.unknown()).optional(),
  algorithm_metadata: z.record(z.unknown()).optional(),
  parent_run_metadata: z.record(z.unknown()).optional(),
});

export type ChildRunSummary = z.infer<typeof ChildRunSummary>;

export function useChildren(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "children", runId] as const,
    queryFn: async () => {
      if (!runId) throw new Error("useChildren: runId is required");
      const response = await fetch(`/runs/${runId}/children`, {
        headers: { accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- /runs/${runId}/children`);
      }
      return parseChildren(await response.json());
    },
    enabled: !!runId,
    refetchInterval: 5_000,
  });
}

function parseChildren(raw: unknown): ChildRunSummary[] {
  const items = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.children)
      ? raw.children
      : [];

  return items.map((item) => {
    if (isRecord(item) && isRecord(item.summary)) {
      return ChildRunSummary.parse({ ...item.summary, ...item });
    }
    return ChildRunSummary.parse(item);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
