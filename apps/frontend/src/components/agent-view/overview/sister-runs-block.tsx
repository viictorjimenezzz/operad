import { PanelCard, Pill, StatusDot } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import { RunInvocationsResponse } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

export interface SisterRunsBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
  runId?: string;
}

export function SisterRunsBlock(props: SisterRunsBlockProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.invocations);
  const rows = parsed.success ? parsed.data.invocations : [];
  const last = rows[rows.length - 1];
  const hashContent = last?.hash_content ?? null;

  const sisterQuery = useQuery({
    queryKey: ["runs", "by-hash", hashContent] as const,
    queryFn: () => dashboardApi.runsByHash(hashContent ?? ""),
    enabled: !!hashContent,
    retry: false,
    staleTime: 30_000,
  });

  const matches = sisterQuery.data?.matches ?? [];
  const otherRuns = matches.filter((m) => m.run_id !== props.runId);
  const titleNode = !hashContent
    ? "no hash_content yet"
    : sisterQuery.isLoading
      ? "searching…"
      : sisterQuery.error
        ? "endpoint unavailable"
        : otherRuns.length === 0
          ? "no other runs share this fingerprint"
          : `${otherRuns.length} other run${otherRuns.length === 1 ? "" : "s"} share this fingerprint`;

  return (
    <PanelCard
      eyebrow="Sister runs"
      title={
        <span className="flex items-center gap-2">
          {titleNode}
          {hashContent && otherRuns.length > 0 ? (
            <Link
              to={`/agents/${hashContent}`}
              className="ml-auto text-[11px] text-accent hover:text-[--color-accent-strong]"
            >
              view group →
            </Link>
          ) : null}
        </span>
      }
    >
      {otherRuns.length === 0 ? null : (
        <ul className="space-y-1.5">
          {otherRuns.slice(0, 8).map((run) => (
            <li
              key={run.run_id}
              className="flex items-center gap-3 rounded-md border border-border px-3 py-2 transition-colors hover:bg-bg-3"
            >
              <StatusDot identity={run.run_id} state={run.state === "running" ? "running" : run.state === "error" ? "error" : "ended"} size="sm" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-[13px]">
                  <span className="font-medium">{run.algorithm_class ?? "Agent"}</span>
                  <span className="font-mono text-[11px] text-muted-2">
                    {truncateMiddle(run.run_id, 16)}
                  </span>
                </div>
                <div className="text-[11px] text-muted-2">{formatRelativeTime(run.started_at)}</div>
              </div>
              {run.state === "running" ? (
                <Pill tone="live" pulse size="sm">live</Pill>
              ) : run.state === "error" ? (
                <Pill tone="error" size="sm">error</Pill>
              ) : null}
              <Link
                to={
                  hashContent
                    ? `/agents/${hashContent}/runs/${run.run_id}`
                    : `/runs/${run.run_id}`
                }
                className="rounded p-1 text-muted-2 hover:text-text"
                aria-label="open run"
              >
                <ExternalLink size={12} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PanelCard>
  );
}
