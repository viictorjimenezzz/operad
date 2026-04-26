import { ReplayControls } from "@/components/panels/replay-controls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { CassetteDeterminismResponse, CassetteSummary } from "@/lib/types";
import { formatNumber, formatRelativeTime } from "@/lib/utils";
import { Link } from "react-router-dom";

interface CassetteListProps {
  items: CassetteSummary[];
  replayingPath: string | null;
  checkingPath: string | null;
  determinismByPath: Record<string, CassetteDeterminismResponse | undefined>;
  onReplay: (path: string) => void;
  onDeterminism: (path: string) => void;
  onRefresh: () => void;
}

function cassetteHref(path: string): string {
  return `/cassettes/${path
    .split("/")
    .map((seg) => encodeURIComponent(seg))
    .join("/")}`;
}

function metadataLine(item: CassetteSummary): string {
  const runId = typeof item.metadata.run_id === "string" ? item.metadata.run_id : null;
  const algorithm = typeof item.metadata.algorithm === "string" ? item.metadata.algorithm : null;
  const parts = [algorithm, runId].filter((x): x is string => x != null && x.length > 0);
  return parts.join(" · ");
}

export function CassetteList({
  items,
  replayingPath,
  checkingPath,
  determinismByPath,
  onReplay,
  onDeterminism,
  onRefresh,
}: CassetteListProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-bg-1 px-4 py-2">
        <h2 className="m-0 text-[0.72rem] uppercase tracking-[0.1em] text-muted">
          all cassettes ({items.length})
        </h2>
        <div className="ml-auto">
          <Button size="sm" onClick={onRefresh}>
            refresh
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3">
        {items.length === 0 ? (
          <EmptyState
            title="no cassettes"
            description="set OPERAD_DASHBOARD_CASSETTE_DIR or add files to ./.cassettes"
          />
        ) : (
          <div className="flex flex-col gap-3">
            {items.map((item) => {
              const meta = metadataLine(item);
              return (
                <section key={item.path} className="rounded-md border border-border bg-bg-1 p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Link
                      to={cassetteHref(item.path)}
                      className="font-mono text-xs text-text hover:text-accent"
                    >
                      {item.path}
                    </Link>
                    <Badge variant="default">{item.type}</Badge>
                    <span className="ml-auto text-[11px] text-muted">
                      {formatNumber(item.size)}B · {formatRelativeTime(item.mtime)}
                    </span>
                  </div>
                  {meta && <div className="mb-2 text-[11px] text-muted">{meta}</div>}
                  <ReplayControls
                    onReplay={() => onReplay(item.path)}
                    onDeterminism={() => onDeterminism(item.path)}
                    replaying={replayingPath === item.path}
                    checking={checkingPath === item.path}
                    result={determinismByPath[item.path] ?? null}
                  />
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
