import { dashboardApi } from "@/lib/api/dashboard";
import type { CassetteDeterminismResponse } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { ReplayControls } from "@/shared/panels/replay-controls";
import { Badge } from "@/shared/ui/badge";
import { EmptyState } from "@/shared/ui/empty-state";
import { JsonView } from "@/shared/ui/json-view";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

function decodeCassettePath(splat: string | undefined): string | null {
  if (!splat) return null;
  return splat
    .split("/")
    .filter((x) => x.length > 0)
    .map((x) => decodeURIComponent(x))
    .join("/");
}

export function CassetteDetailPage() {
  const navigate = useNavigate();
  const params = useParams();
  const cassettePath = decodeCassettePath(params["*"]);

  const [replaying, setReplaying] = useState(false);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<CassetteDeterminismResponse | null>(null);

  const list = useQuery({
    queryKey: ["cassettes"] as const,
    queryFn: () => dashboardApi.cassettes(),
  });
  const preview = useQuery({
    queryKey: ["cassettes", "preview", cassettePath] as const,
    queryFn: () => {
      if (!cassettePath) throw new Error("missing cassette path");
      return dashboardApi.cassettePreview(cassettePath, 100);
    },
    enabled: !!cassettePath,
  });

  if (!cassettePath) return <EmptyState title="missing cassette path" />;

  const item = (list.data ?? []).find((x) => x.path === cassettePath) ?? null;

  const onReplay = () => {
    setReplaying(true);
    void dashboardApi
      .cassetteReplay({ path: cassettePath, delayMs: 50 })
      .then((res) => navigate(`/runs/${res.run_id}`))
      .finally(() => setReplaying(false));
  };

  const onDeterminism = () => {
    setChecking(true);
    void dashboardApi
      .cassetteDeterminism(cassettePath)
      .then((res) => setResult(res))
      .finally(() => setChecking(false));
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-4 py-2 text-xs">
        <Link to="/cassettes" className="text-muted hover:text-text">
          ← cassettes
        </Link>
        <span className="text-muted">/</span>
        <span className="font-mono text-text">{cassettePath}</span>
        {item && <Badge variant="default">{item.type}</Badge>}
        {item && <span className="ml-auto text-muted">{formatRelativeTime(item.mtime)}</span>}
      </div>

      <div className="flex flex-col gap-3 overflow-auto p-3">
        <section className="rounded-md border border-border bg-bg-1 p-3">
          <ReplayControls
            onReplay={onReplay}
            onDeterminism={onDeterminism}
            replaying={replaying}
            checking={checking}
            result={result}
          />
          {item?.metadata && Object.keys(item.metadata).length > 0 && (
            <div className="mt-3">
              <div className="mb-1 text-[11px] uppercase tracking-[0.08em] text-muted">metadata</div>
              <JsonView value={item.metadata} collapsed />
            </div>
          )}
        </section>

        <section className="rounded-md border border-border bg-bg-1 p-3">
          <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">
            recorded events preview (first 100)
          </div>
          {preview.isLoading ? (
            <div className="text-xs text-muted">loading events…</div>
          ) : (
            <JsonView value={preview.data?.events ?? []} />
          )}
        </section>
      </div>
    </div>
  );
}
