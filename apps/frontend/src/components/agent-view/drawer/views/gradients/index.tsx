import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi } from "@/lib/api/dashboard";
import type { DrawerPayload } from "@/stores/ui";
import { useQuery } from "@tanstack/react-query";
import { registerDrawerView } from "@/components/agent-view/drawer/drawer-registry";

function matchesParam(paramPath: string, entry: { target_paths: string[]; by_field: Record<string, string> }): boolean {
  const direct = entry.target_paths.some(
    (p) => p === paramPath || p.endsWith(`.${paramPath}`) || paramPath.endsWith(`.${p}`),
  );
  if (direct) return true;
  return Object.keys(entry.by_field).some(
    (field) =>
      field === paramPath || field.endsWith(`.${paramPath}`) || paramPath.endsWith(`.${field}`),
  );
}

function severityLabel(severity: number): string {
  if (severity >= 0.75) return "high";
  if (severity >= 0.4) return "medium";
  if (severity > 0) return "low";
  return "none";
}

function GradientsView({ payload, runId }: { payload: DrawerPayload; runId: string }) {
  const paramPath = typeof payload.paramPath === "string" ? payload.paramPath : null;

  const query = useQuery({
    queryKey: ["run", "gradients", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("runId is required");
      return dashboardApi.gradients(runId);
    },
    enabled: !!runId,
  });

  if (!paramPath) {
    return <EmptyState title="missing parameter path" description="open this drawer from a parameter gradient pill" />;
  }
  if (query.isPending) return <div className="p-3 text-xs text-muted">loading gradients…</div>;
  if (query.isError || !query.data) {
    return <EmptyState title="failed to load gradients" description="check backend logs for /runs/{id}/gradients.json" />;
  }

  const rows = query.data
    .filter((entry) => matchesParam(paramPath, entry))
    .sort((a, b) => b.epoch - a.epoch || b.batch - a.batch);

  if (rows.length === 0) {
    return <EmptyState title="no gradients for this parameter" description={paramPath} />;
  }

  return (
    <div className="space-y-2 p-3">
      <div className="text-xs text-muted">{paramPath}</div>
      {rows.map((entry, idx) => (
        <div key={`${entry.epoch}:${entry.batch}:${idx}`} className="rounded border border-border bg-bg-2 p-2">
          <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
            <span className="text-muted">
              epoch {entry.epoch} batch {entry.batch}
            </span>
            <span className="rounded border border-border px-1 py-0.5 uppercase text-muted">
              {severityLabel(entry.severity)} {entry.severity.toFixed(2)}
            </span>
          </div>
          <p className="m-0 whitespace-pre-wrap text-xs text-text">{entry.message || "(empty message)"}</p>
        </div>
      ))}
    </div>
  );
}

registerDrawerView("gradients", {
  getTitle: () => "Gradient rationale",
  getSubtitle: (payload) => (typeof payload.paramPath === "string" ? payload.paramPath : null),
  render: ({ payload, runId }) => <GradientsView payload={payload} runId={runId} />,
});

export { GradientsView };
