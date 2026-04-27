import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { PanelCard } from "@/components/ui/panel-card";
import { PanelGrid } from "@/components/ui/panel-grid";
import { StatusDot } from "@/components/ui/status-dot";
import { IterationsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import { formatDurationMs } from "@/lib/utils";
import { ExternalLink } from "lucide-react";

interface VerifierDetailOverviewProps {
  dataSummary: unknown;
  dataIterations: unknown;
  runId: string;
}

export function VerifierDetailOverview({
  dataSummary,
  dataIterations,
  runId,
}: VerifierDetailOverviewProps) {
  const summary = RunSummarySchema.safeParse(dataSummary);
  const iterations = IterationsResponse.safeParse(dataIterations);

  if (!summary.success || !iterations.success) {
    return <EmptyState title="no verifier data" description="waiting for verifier events" />;
  }

  const rows = iterations.data.iterations;
  const final = [...rows].reverse().find((row) => row.text || row.score != null);
  const hash = summary.data.root_agent_path ?? summary.data.run_id;
  const agentHref = `/agents/${encodeURIComponent(hash)}/runs/${encodeURIComponent(runId)}`;

  return (
    <div className="flex flex-col gap-3">
      <PanelCard>
        <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted">
          <span className="inline-flex items-center gap-2">
            <StatusDot state={summary.data.state} />
            <span className="font-mono text-text">{summary.data.state}</span>
          </span>
          <Metric label="threshold" value={formatMetric(iterations.data.threshold)} />
          <Metric label="max_iter" value={iterations.data.max_iter?.toString() ?? "-"} />
          <Metric label="iters" value={rows.length.toString()} />
          <Metric label="converged" value={iterations.data.converged ? "yes" : "no"} />
          <Metric label="final score" value={formatMetric(final?.score ?? null)} />
          <Metric label="wall" value={formatDurationMs(summary.data.duration_ms)} />
        </div>
      </PanelCard>

      <PanelGrid cols={2}>
        <PanelCard title="accepted answer">
          <MarkdownView value={final?.text ?? ""} />
        </PanelCard>
        <PanelCard title="threshold vs score" bodyMinHeight={220}>
          <ConvergenceCurve data={iterations.data} height={220} />
        </PanelCard>
      </PanelGrid>

      <PanelCard title="agent duality">
        <div className="flex flex-wrap items-center gap-3 text-[12px] text-muted">
          <span>
            This VerifierAgent run is both an algorithm run and an agent run with the same run id.
          </span>
          <a href={agentHref}>
            <Button size="sm" variant="outline">
              <ExternalLink size={13} />
              Open agent view
            </Button>
          </a>
        </div>
      </PanelCard>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <span>
      {label}=<span className="font-mono text-text">{value}</span>
    </span>
  );
}

function formatMetric(value: number | null | undefined): string {
  return value == null ? "-" : value.toFixed(3);
}
