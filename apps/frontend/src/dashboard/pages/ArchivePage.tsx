import { useArchiveRuns } from "@/hooks/use-runs";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { EmptyState } from "@/shared/ui/empty-state";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

export function ArchivePage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [algorithm, setAlgorithm] = useState("");

  const params = useMemo(() => {
    const next: { from?: number; to?: number; algorithm?: string; limit: number } = { limit: 200 };
    if (from.trim()) next.from = Number(from);
    if (to.trim()) next.to = Number(to);
    if (algorithm.trim()) next.algorithm = algorithm.trim();
    return next;
  }, [from, to, algorithm]);

  const archive = useArchiveRuns(params);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-4 py-2 text-xs">
        <Link to="/" className="text-muted hover:text-text">
          ← live runs
        </Link>
        <span className="text-muted">/</span>
        <span className="font-medium text-text">archive</span>
      </div>
      <div className="grid grid-cols-[1fr_1fr_1fr] gap-2 border-b border-border bg-bg-1 px-4 py-2">
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          from (unix seconds)
          <input
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="rounded border border-border bg-bg-2 px-2 py-1 text-xs text-text"
            placeholder="optional"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          to (unix seconds)
          <input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="rounded border border-border bg-bg-2 px-2 py-1 text-xs text-text"
            placeholder="optional"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] text-muted">
          algorithm (class or path)
          <input
            value={algorithm}
            onChange={(e) => setAlgorithm(e.target.value)}
            className="rounded border border-border bg-bg-2 px-2 py-1 text-xs text-text"
            placeholder="EvoGradient"
          />
        </label>
      </div>

      <div className="flex-1 overflow-auto">
        {archive.isLoading ? <div className="p-4 text-xs text-muted">loading archive…</div> : null}
        {archive.error ? (
          <EmptyState title="failed to load archive" description="check dashboard archive backend" />
        ) : null}
        {!archive.isLoading && !archive.error && (archive.data?.length ?? 0) === 0 ? (
          <EmptyState title="archive is empty" description="terminal runs appear here after completion" />
        ) : null}
        {archive.data && archive.data.length > 0 ? (
          <ul>
            {archive.data.map((run) => (
              <li key={run.run_id} className="border-b border-border/60">
                <Link
                  to={`/archive/${run.run_id}`}
                  className="flex items-center gap-2 px-4 py-2 text-xs hover:bg-bg-2"
                >
                  <span className="min-w-0 flex-1 font-mono text-text">
                    {truncateMiddle(run.run_id, 28)}
                  </span>
                  {run.algorithm_class ? <Badge variant="algo">{run.algorithm_class}</Badge> : null}
                  <Badge
                    variant={
                      run.state === "running" ? "live" : run.state === "error" ? "error" : "ended"
                    }
                  >
                    {run.state}
                  </Badge>
                  <span className="text-muted">{formatRelativeTime(run.started_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
