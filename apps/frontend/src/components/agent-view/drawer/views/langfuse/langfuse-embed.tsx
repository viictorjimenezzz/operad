import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useManifest } from "@/hooks/use-runs";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";

export interface LangfuseEmbedProps {
  runId: string;
  payload: Record<string, unknown>;
  className?: string;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function buildLangfuseHref(
  baseUrl: string,
  payload: Record<string, unknown>,
): { href: string; path: string | null } {
  const base = baseUrl.replace(/\/$/, "");
  const invocationId = asString(payload.invocationId);
  const agentPath = asString(payload.agentPath);

  if (invocationId) {
    return { href: `${base}/trace/${encodeURIComponent(invocationId)}`, path: agentPath };
  }
  if (agentPath) {
    return { href: `${base}/traces?search=${encodeURIComponent(agentPath)}`, path: agentPath };
  }
  return { href: base, path: null };
}

export function LangfuseEmbed({ runId, payload, className }: LangfuseEmbedProps) {
  const manifest = useManifest();
  const baseUrl = manifest.data?.langfuseUrl ?? null;
  const [refreshKey, setRefreshKey] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  const target = useMemo(() => {
    if (!baseUrl) return null;
    return buildLangfuseHref(baseUrl, payload);
  }, [baseUrl, payload]);

  if (!baseUrl || !target) {
    return (
      <div className={`h-full p-3 ${className ?? ""}`.trim()}>
        <EmptyState
          title="Langfuse is not configured"
          description="Set LANGFUSE_PUBLIC_URL to enable the embedded trace view."
          cta={
            <a
              href="/apps/README.md#self-hosted-observability-stack"
              className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
            >
              observability setup guide <ExternalLink size={12} />
            </a>
          }
        />
      </div>
    );
  }

  useEffect(() => {
    if (loaded || failed) return;
    const timer = window.setTimeout(() => setFailed(true), 7_500);
    return () => window.clearTimeout(timer);
  }, [failed, loaded, refreshKey]);

  const showFallback = failed;

  return (
    <div className={`flex h-full min-h-0 flex-col gap-2 p-3 ${className ?? ""}`.trim()}>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => window.open(target.href, "_blank", "noopener")}
        >
          <ExternalLink size={12} />
          Open in Langfuse
        </Button>
        <span className="min-w-0 flex-1 truncate rounded border border-border bg-bg-2 px-2 py-1 font-mono text-[11px] text-muted">
          {target.path ?? runId}
        </span>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Refresh Langfuse frame"
          onClick={() => {
            setLoaded(false);
            setFailed(false);
            setRefreshKey((k) => k + 1);
          }}
        >
          <RefreshCw size={13} />
        </Button>
      </div>

      {showFallback ? (
        <div className="flex flex-1 items-center justify-center rounded-md border border-border bg-bg-2 p-4">
          <EmptyState
            title="Unable to embed Langfuse"
            description="This deployment may block iframe embedding."
            cta={
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(target.href, "_blank", "noopener")}
              >
                <ExternalLink size={12} />
                Open externally
              </Button>
            }
          />
        </div>
      ) : (
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-md border border-border bg-bg-2">
          {!loaded ? <div className="absolute inset-0 animate-pulse bg-bg-2" aria-label="loading" /> : null}
          <iframe
            key={refreshKey}
            title="Langfuse"
            src={target.href}
            className="h-full w-full"
            sandbox="allow-forms allow-scripts allow-popups allow-popups-to-escape-sandbox"
            referrerPolicy="no-referrer"
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
          />
        </div>
      )}
    </div>
  );
}

export { buildLangfuseHref };
