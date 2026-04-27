import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { StatusDot } from "@/components/ui/status-dot";
import { IterationsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import type { RunSummary } from "@/lib/types";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

export function SelfRefineDetailOverview({
  dataSummary,
  dataIterations,
  dataChildren,
}: {
  dataSummary?: unknown;
  dataIterations?: unknown;
  dataChildren?: unknown;
}) {
  const summaryParsed = RunSummarySchema.safeParse(dataSummary);
  const iterationsParsed = IterationsResponse.safeParse(dataIterations);
  const summary = summaryParsed.success ? summaryParsed.data : null;
  const iterations = iterationsParsed.success ? iterationsParsed.data : null;
  const children = parseChildren(dataChildren);
  const finalText = finalAnswer(iterations?.iterations ?? []);
  const finalChild = finalAnswerChild(children, iterations?.iterations ?? []);
  const [, setSearchParams] = useSearchParams();

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px]">
        <span className="inline-flex items-center gap-2 font-medium text-text">
          <StatusDot state={summary?.state ?? "running"} />
          {summary?.state ?? "running"}
        </span>
        <span className="text-muted">
          max_iter <span className="font-mono text-text">{iterations?.max_iter ?? "n/a"}</span>
        </span>
        <span className="text-muted">
          iters used{" "}
          <span className="font-mono text-text">{iterations?.iterations.length ?? "n/a"}</span>
        </span>
        <span className="text-muted">
          converged{" "}
          <span className="font-mono text-text">{String(iterations?.converged ?? false)}</span>
        </span>
        <span className="text-muted">
          final score{" "}
          <span className="font-mono text-text">{formatScore(finalScore(iterations))}</span>
        </span>
      </div>

      <section className="rounded-lg border border-border bg-bg-1 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="m-0 text-[15px] font-semibold text-text">Final answer</h2>
            <p className="m-0 mt-1 text-[11px] text-muted">Last accepted or refined draft</p>
          </div>
          {finalChild ? (
            <a
              className="rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
              href={childHref(finalChild)}
            >
              Open generator run
            </a>
          ) : null}
        </div>
        {finalText ? (
          <MarkdownView value={finalText} />
        ) : (
          <EmptyState
            title="final answer not available"
            description="no refinement text has been recorded yet"
            className="min-h-32"
          />
        )}
      </section>

      <button
        type="button"
        className="rounded-lg border border-border bg-bg-1 p-3 text-left transition-colors hover:border-border-strong"
        onClick={() =>
          setSearchParams(
            (current) => {
              const next = new URLSearchParams(current);
              next.set("tab", "convergence");
              return next;
            },
            { replace: true },
          )
        }
      >
        <div className="mb-2 text-[12px] font-medium text-text">Score trajectory</div>
        <ConvergenceCurve data={dataIterations} height={160} />
      </button>
    </div>
  );
}

function parseChildren(data: unknown): RunSummary[] {
  const raw = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).children)
      ? (data as Record<string, unknown>).children
      : [];
  const parsed = z.array(RunSummarySchema).safeParse(raw);
  return parsed.success ? parsed.data : [];
}

function finalAnswer(entries: IterationsResponse["iterations"]): string | null {
  for (let i = entries.length - 1; i >= 0; i--) {
    const text = entries[i]?.text;
    if (text) return text;
  }
  return null;
}

function finalScore(data: IterationsResponse | null): number | null {
  const entries = data?.iterations ?? [];
  for (let i = entries.length - 1; i >= 0; i--) {
    const score = entries[i]?.score;
    if (score != null) return score;
  }
  return null;
}

function finalAnswerChild(
  children: RunSummary[],
  entries: IterationsResponse["iterations"],
): RunSummary | null {
  const lastIter = entries.length > 0 ? Math.max(...entries.map((entry) => entry.iter_index)) : 0;
  const index = lastIter === 0 ? 0 : lastIter * 2;
  return children[index] ?? null;
}

function childHref(child: RunSummary): string {
  const identity = child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
