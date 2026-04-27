import { Button } from "@/components/ui/button";
import { MarkdownView } from "@/components/ui/markdown";
import { PanelCard } from "@/components/ui/panel-card";
import { type Candidate, RunSummary as RunSummarySchema } from "@/lib/types";
import { formatCost, formatDurationMs } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface CriticRationaleCardProps {
  candidate: Candidate;
  generatorRun?: ChildRunSummary | null;
  criticRun?: ChildRunSummary | null;
  rank?: number;
  topK?: boolean;
}

export function CriticRationaleCard({
  candidate,
  generatorRun,
  criticRun,
  rank,
  topK,
}: CriticRationaleCardProps) {
  const rationale = useCriticRationale(criticRun?.run_id ?? null);
  const generatorHref = generatorRun ? childHref(generatorRun) : null;
  const criticHref = criticRun ? childHref(criticRun) : null;

  return (
    <PanelCard
      title={`candidate #${candidate.candidate_index ?? "?"}${topK ? " selected" : ""}`}
      eyebrow={rank != null ? `rank ${rank}` : undefined}
    >
      <div className="flex flex-col gap-3">
        <div className="grid gap-2 text-[12px] md:grid-cols-4">
          <Meta label="generator" value={runLabel(generatorRun)} />
          <Meta label="cost" value={formatCost(generatorRun?.cost?.cost_usd ?? null)} />
          <Meta label="latency" value={formatDurationMs(generatorRun?.duration_ms ?? null)} />
          <Meta
            label="judge score"
            value={candidate.score != null ? candidate.score.toFixed(3) : "unscored"}
          />
        </div>
        <div>
          <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
            Full text
          </div>
          <MarkdownView value={candidate.text ?? ""} />
        </div>
        {criticRun ? (
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
              Judge rationale
            </div>
            {rationale.isLoading ? (
              <div className="text-[12px] text-muted">loading rationale...</div>
            ) : (
              <MarkdownView
                value={rationale.data || "No rationale captured for this critic run."}
              />
            )}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {generatorHref ? (
            <a href={generatorHref}>
              <Button size="sm">
                <ExternalLink size={13} />
                Open generator run
              </Button>
            </a>
          ) : null}
          {criticHref ? (
            <a href={criticHref}>
              <Button size="sm" variant="outline">
                <ExternalLink size={13} />
                Open critic run
              </Button>
            </a>
          ) : null}
        </div>
      </div>
    </PanelCard>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-bg-inset px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">{label}</div>
      <div className="truncate font-mono text-text">{value}</div>
    </div>
  );
}

function useCriticRationale(runId: string | null) {
  return useQuery({
    queryKey: ["run", "critic-rationale", runId] as const,
    queryFn: async () => {
      if (!runId) return "";
      const response = await fetch(`/runs/${runId}/events?limit=100`);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- /runs/${runId}/events`);
      }
      const parsed = z
        .object({ events: z.array(z.record(z.unknown())).default([]) })
        .parse(await response.json());
      for (let i = parsed.events.length - 1; i >= 0; i -= 1) {
        const event = parsed.events[i];
        if (!event || event.kind !== "end") continue;
        const text = textFromUnknown(event.output);
        if (text) return text;
      }
      return "";
    },
    enabled: Boolean(runId),
    staleTime: 30_000,
  });
}

function textFromUnknown(value: unknown): string {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  const obj = value as Record<string, unknown>;
  for (const key of ["rationale", "critique", "feedback", "reasoning", "answer"]) {
    const candidate = obj[key];
    if (typeof candidate === "string" && candidate.trim()) return candidate;
  }
  return JSON.stringify(value, null, 2);
}

function runLabel(run: ChildRunSummary | null | undefined): string {
  if (!run) return "unknown";
  return run.root_agent_path?.split(".").at(-1) ?? run.algorithm_class ?? run.run_id;
}

function childHref(child: ChildRunSummary): string {
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

export type { ChildRunSummary };
