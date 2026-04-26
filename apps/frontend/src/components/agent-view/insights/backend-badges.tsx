import { Chip } from "@/components/ui/chip";
import type { AgentMetaResponse, RunInvocation } from "@/lib/types";
import { useUIStore } from "@/stores/ui";

export interface BackendBadgesProps {
  invocations: RunInvocation[];
  summaryRaw: unknown;
  meta: AgentMetaResponse | null;
}

export function BackendBadges({ invocations, summaryRaw, meta }: BackendBadgesProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const latest = invocations[invocations.length - 1] ?? null;
  const backend = asString(meta?.config.backend) ?? asString(latest?.backend) ?? "unknown";
  const model = asString(meta?.config.model) ?? asString(latest?.model) ?? "unknown model";
  const sampling = meta?.config.sampling ?? {};
  const io = meta?.config.io ?? {};
  const runtime = meta?.config.runtime ?? {};
  const temperature = asNumber(sampling.temperature);
  const topP = asNumber(sampling.top_p);
  const renderer = asString(runtime.renderer) ?? asString(latest?.renderer) ?? "xml";
  const runtimeExtra = asRecord(runtime.extra);
  const isLocal =
    backend.toLowerCase().includes("llama") ||
    backend.toLowerCase().includes("ollama") ||
    backend.toLowerCase().includes("lmstudio") ||
    backend.toLowerCase().includes("local");
  const hasStructured = Boolean(io.structured || io.structured_io);
  const cassetteMode = cassetteModeFromSummary(summaryRaw);

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-bg-1 p-3">
      <Chip>{backend}</Chip>
      {isLocal ? <Chip>local</Chip> : null}
      <Chip>{model}</Chip>
      {temperature != null ? <Chip>{`T ${temperature}`}</Chip> : null}
      {topP != null ? <Chip>{`top_p ${topP}`}</Chip> : null}
      {hasStructured ? <Chip>structured</Chip> : null}
      <Chip>{renderer}</Chip>
      {Object.keys(sampling).length > 0 ? <Chip title="default sampling overrides">*</Chip> : null}
      {cassetteMode ? <Chip>{`cassette ${cassetteMode}`}</Chip> : null}
      {runtimeExtra ? (
        <button
          type="button"
          className="rounded-full border border-border bg-bg-2 px-2.5 py-0.5 text-[0.72rem] tracking-[0.03em] text-muted hover:text-text"
          onClick={() => {
            if (!meta) return;
            openDrawer("events", { agentPath: meta.agent_path, panel: "config" });
          }}
        >
          +{Object.keys(runtimeExtra).length}
        </button>
      ) : null}
    </div>
  );
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function cassetteModeFromSummary(summaryRaw: unknown): string | null {
  if (!summaryRaw || typeof summaryRaw !== "object") return null;
  const summary = summaryRaw as Record<string, unknown>;
  const explicit = summary.cassette_mode;
  if (typeof explicit === "string" && explicit.length > 0) return explicit;
  return summary.synthetic === true ? "replay" : null;
}
