import { Pill } from "@/components/ui/pill";
import { useManifest } from "@/hooks/use-runs";

export function CassetteRibbon() {
  const manifest = useManifest();
  if (manifest.isLoading || !manifest.data) return null;

  const showCassette = manifest.data.cassetteMode === true;
  const showTrace = typeof manifest.data.tracePath === "string" && manifest.data.tracePath.length > 0;
  if (!showCassette && !showTrace) return null;

  return (
    <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-3 py-1 text-[11px]">
      {showCassette ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[--color-warn]" />
          cassette: enabled
          {manifest.data.cassettePath ? (
            <code className="font-mono text-muted-2">{manifest.data.cassettePath}</code>
          ) : null}
          {manifest.data.cassetteStale ? (
            <Pill size="sm" tone="error">
              stale
            </Pill>
          ) : null}
        </span>
      ) : null}
      {showTrace ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[--color-accent]" />
          trace:
          <code className="font-mono text-muted-2">{manifest.data.tracePath}</code>
        </span>
      ) : null}
    </div>
  );
}
