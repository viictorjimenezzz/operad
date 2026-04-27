import { SynthesisCard } from "@/components/algorithms/debate/synthesis-card";
import { DebateConsensusTracker } from "@/components/charts/debate-consensus-tracker";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusDot } from "@/components/ui/status-dot";
import { DebateRoundsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import type { RunSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});
type ChildRunSummary = z.infer<typeof ChildRunSummary>;

export function DebateDetailOverview({
  dataSummary,
  dataDebate,
  dataChildren,
}: {
  dataSummary?: unknown;
  dataDebate?: unknown;
  dataChildren?: unknown;
}) {
  const summary = RunSummarySchema.safeParse(dataSummary).success
    ? RunSummarySchema.parse(dataSummary)
    : null;
  const rounds = DebateRoundsResponse.safeParse(dataDebate).success
    ? DebateRoundsResponse.parse(dataDebate)
    : [];
  const children = parseChildren(dataChildren);
  const synthesizer = findChild(children, "synth");
  const synthesis = useChildAnswer(synthesizer);
  const proposerCount =
    rounds[0]?.proposals.length ??
    (summary?.event_counts.algo_start != null ? Number(summary.event_counts.algo_start) : null);

  return (
    <div className="flex flex-col gap-4 p-4">
      <StatusStrip summary={summary} rounds={rounds.length} proposers={proposerCount} />

      <SynthesisCard
        answer={synthesis.answer}
        childHref={childHref(synthesizer)}
        loading={synthesis.loading}
      />

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 text-[12px] font-medium text-text">Consensus progression</div>
          <DebateConsensusTracker data={rounds} height={180} />
        </div>
        <div className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 text-[12px] font-medium text-text">Topic</div>
          <EmptyState
            title="topic not recorded"
            description="debate round events include proposals, critiques, and scores, but not the original topic"
            className="min-h-32"
          />
        </div>
      </section>
    </div>
  );
}

function StatusStrip({
  summary,
  rounds,
  proposers,
}: {
  summary: RunSummary | null;
  rounds: number;
  proposers: number | null;
}) {
  const state = summary?.state ?? "running";
  const duration = formatDuration(summary?.duration_ms ?? null);
  const totalCost = summary?.cost?.cost_usd;
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px]">
      <span className="inline-flex items-center gap-2 font-medium text-text">
        <StatusDot state={state} />
        {state}
      </span>
      <span className="text-muted">
        rounds <span className="font-mono text-text">{rounds}</span>
      </span>
      <span className="text-muted">
        proposers <span className="font-mono text-text">{proposers ?? "n/a"}</span>
      </span>
      <span className="text-muted">
        wall <span className="font-mono text-text">{duration}</span>
      </span>
      <span className="text-muted">
        total cost{" "}
        <span className="font-mono text-text">
          {typeof totalCost === "number" ? `$${totalCost.toFixed(4)}` : "n/a"}
        </span>
      </span>
    </div>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const raw = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).children)
      ? (data as Record<string, unknown>).children
      : [];
  return z.array(ChildRunSummary).safeParse(raw).success ? z.array(ChildRunSummary).parse(raw) : [];
}

function findChild(children: ChildRunSummary[], needle: string): ChildRunSummary | null {
  const lower = needle.toLowerCase();
  return (
    children.find((child) => (child.root_agent_path ?? "").toLowerCase().includes(lower)) ??
    children.find((child) => (child.algorithm_class ?? "").toLowerCase().includes(lower)) ??
    null
  );
}

function useChildAnswer(child: ChildRunSummary | null): {
  answer: string | null;
  loading: boolean;
} {
  const query = useQuery({
    queryKey: ["algorithm", "debate", "synthesis", child?.run_id] as const,
    queryFn: async () => {
      if (!child) return null;
      const response = await fetch(`/runs/${child.run_id}/invocations`);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const data = (await response.json()) as unknown;
      return extractLatestOutput(data);
    },
    enabled: child != null,
  });
  return { answer: query.data ?? null, loading: query.isLoading };
}

function extractLatestOutput(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const invocations = (data as Record<string, unknown>).invocations;
  if (!Array.isArray(invocations)) return null;
  for (let i = invocations.length - 1; i >= 0; i--) {
    const invocation = invocations[i];
    if (!invocation || typeof invocation !== "object") continue;
    const output = (invocation as Record<string, unknown>).output;
    const text = outputText(output);
    if (text) return text;
  }
  return null;
}

function outputText(output: unknown): string | null {
  if (typeof output === "string") return output;
  if (!output || typeof output !== "object") return null;
  const record = output as Record<string, unknown>;
  for (const key of ["answer", "text", "content"]) {
    const value = record[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function childHref(child: ChildRunSummary | null): string | null {
  if (!child) return null;
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "n/a";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}
