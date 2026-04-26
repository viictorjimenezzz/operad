import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { MetaList } from "@/components/ui/meta-list";
import { RunSummary } from "@/lib/types";
import { formatDurationMs, truncateMiddle } from "@/lib/utils";

export function MetaListPanel({ data }: { data: unknown }) {
  const parsed = RunSummary.safeParse(data);
  if (!parsed.success) return <EmptyState title="no run summary" />;
  const s = parsed.data;
  return (
    <MetaList
      items={[
        {
          label: "run_id",
          value: <span className="font-mono">{truncateMiddle(s.run_id, 14)}</span>,
        },
        {
          label: "state",
          value: (
            <Badge
              variant={s.state === "running" ? "live" : s.state === "error" ? "error" : "ended"}
            >
              {s.state}
            </Badge>
          ),
        },
        { label: "algorithm", value: s.algorithm_path ?? <span className="text-muted-2">—</span> },
        {
          label: "root agent",
          value: s.root_agent_path ?? <span className="text-muted-2">—</span>,
        },
        {
          label: "script",
          value: s.script ? (
            <span className="font-mono">{s.script}</span>
          ) : (
            <span className="text-muted-2">—</span>
          ),
        },
        { label: "duration", value: formatDurationMs(s.duration_ms) },
        ...(s.algorithm_terminal_score != null
          ? [{ label: "score", value: s.algorithm_terminal_score.toFixed(3) }]
          : []),
      ]}
    />
  );
}
