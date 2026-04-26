import { useBenchmarkDelete, useBenchmarks } from "@/hooks/use-runs";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Link } from "react-router-dom";

function fmtTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}

export function BenchmarksPage() {
  const list = useBenchmarks();
  const del = useBenchmarkDelete();

  if (list.isLoading) return <div className="p-6 text-xs text-muted">loading benchmarks…</div>;
  if (list.error) return <EmptyState title="failed to load benchmarks" />;

  const rows = list.data ?? [];

  if (!rows.length) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no benchmarks yet"
          description={
            <>
              ingest a benchmark report:
              <br />
              <code className="mt-1 block rounded bg-bg-2 px-1.5 py-1 font-mono text-[10px]">
                curl -X POST http://localhost:7860/benchmarks/_ingest -d @report.json
              </code>
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center gap-3 border-b border-border pb-2 text-xs">
        <Link to="/" className="text-muted hover:text-text">
          ← runs
        </Link>
        <span className="text-muted">/ benchmarks</span>
      </div>

      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.id} className="rounded border border-border bg-bg-1 p-3">
            <div className="mb-2 flex items-center gap-2">
              <Link to={`/benchmarks/${row.id}`} className="font-mono text-text hover:text-accent">
                {row.name}
              </Link>
              {row.tag ? (
                <span className="rounded bg-bg-3 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.08em] text-warn">
                  tag {row.tag}
                </span>
              ) : null}
              <span className="ml-auto text-[11px] text-muted">
                {row.n_tasks} tasks · {row.n_methods} methods · {fmtTs(row.created_at)}
              </span>
            </div>

            <div className="mb-2 text-[11px] text-muted">{row.summary}</div>

            <div className="mb-2 flex flex-wrap gap-2 text-[11px]">
              {row.leaderboard.map((l) => (
                <span key={`${row.id}:${l.task}`} className="rounded bg-bg-2 px-2 py-1 text-muted">
                  {l.task}: <span className="font-mono text-text">{l.method}</span> ({l.mean.toFixed(3)})
                </span>
              ))}
            </div>

            <div className="flex gap-2">
              <Link to={`/benchmarks/${row.id}`}>
                <Button variant="primary" size="sm">
                  open
                </Button>
              </Link>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => del.mutate(row.id)}
                disabled={del.isPending}
              >
                delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
