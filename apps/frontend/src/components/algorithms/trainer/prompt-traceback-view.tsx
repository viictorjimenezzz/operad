import { CollapsibleSection, EmptyState, MarkdownView, PanelCard, Pill } from "@/components/ui";
import { formatNumber } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

interface PromptTracebackViewProps {
  runId: string;
  dataSummary?: unknown;
}

const TracebackFrame = z.object({
  agent_path: z.string(),
  depth: z.number().default(0),
  is_leaf: z.boolean().default(false),
  input: z.unknown().nullable().optional(),
  output: z.unknown().nullable().optional(),
  rendered_prompt: z.string().nullable().optional(),
  gradient: z
    .object({
      message: z.string().default(""),
      severity: z.number().default(0),
      target_paths: z.array(z.string()).default([]),
      by_field: z.record(z.string()).default({}),
    })
    .nullable()
    .default(null),
});

type TracebackFrame = z.infer<typeof TracebackFrame>;

export function PromptTracebackView({ runId, dataSummary }: PromptTracebackViewProps) {
  const hasTraceback = hasTracebackArtifact(dataSummary);
  const query = useQuery({
    queryKey: ["run", "traceback", runId] as const,
    queryFn: () => fetchTraceback(runId),
    enabled: Boolean(runId) && hasTraceback !== false,
    retry: false,
  });

  if (hasTraceback === false) {
    return (
      <EmptyState
        title="no traceback artifact"
        description="this Trainer run has not persisted PromptTraceback frames"
      />
    );
  }
  if (query.isLoading) return <div className="text-xs text-muted">loading traceback...</div>;
  if (query.error) {
    return (
      <EmptyState
        title="traceback unavailable"
        description="the persisted PromptTraceback artifact could not be loaded"
      />
    );
  }

  const frames = query.data ?? [];
  if (frames.length === 0) {
    return (
      <EmptyState
        title="empty traceback"
        description="the artifact loaded but did not contain frames"
      />
    );
  }

  return (
    <div className="space-y-3">
      <TracebackToolbar runId={runId} dataSummary={dataSummary} />
      <PanelCard title={tracebackTitle(dataSummary)}>
        <div className="space-y-2">
          {frames.map((frame, index) => (
            <CollapsibleSection
              key={`${frame.agent_path}-${index}`}
              id={`traceback-${index}`}
              label={`Frame ${index + 1}`}
              preview={
                <span className="inline-flex min-w-0 items-center gap-2">
                  <span className="truncate font-mono">{frame.agent_path}</span>
                  {frame.gradient ? (
                    <span className="font-mono text-muted">
                      severity {formatNumber(frame.gradient.severity)}
                    </span>
                  ) : null}
                </span>
              }
              defaultOpen={index === 0}
            >
              <TracebackFrameView frame={frame} />
            </CollapsibleSection>
          ))}
        </div>
      </PanelCard>
    </div>
  );
}

function TracebackToolbar({ runId, dataSummary }: { runId: string; dataSummary?: unknown }) {
  const studioUrl = summaryString(dataSummary, ["studio_url", "studioUrl"]);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <a
        href={`/runs/${encodeURIComponent(runId)}/traceback`}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted transition-colors hover:border-border-strong hover:text-text"
      >
        Open as NDJSON
      </a>
      {studioUrl ? (
        <a
          href={studioUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-accent transition-colors hover:border-border-strong"
        >
          Open in Studio
        </a>
      ) : (
        <button
          type="button"
          disabled
          title="Studio link unavailable for this run"
          className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted opacity-70"
        >
          Open in Studio
        </button>
      )}
    </div>
  );
}

function TracebackFrameView({ frame }: { frame: TracebackFrame }) {
  return (
    <div className="space-y-3 text-[12px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-text">{frame.agent_path}</span>
        <Pill tone={frame.is_leaf ? "default" : "accent"}>{frame.is_leaf ? "leaf" : "router"}</Pill>
      </div>
      <TracebackValue label="inputs" value={frame.input} />
      <TracebackValue label="output" value={frame.output} />
      {frame.rendered_prompt ? (
        <TracebackValue label="prompt" value={frame.rendered_prompt} />
      ) : null}
      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
          gradient
        </div>
        {frame.gradient ? (
          <div className="space-y-2 rounded border border-border bg-bg-2 p-2">
            <div className="font-mono text-[11px] text-muted">
              severity {formatNumber(frame.gradient.severity)}
            </div>
            <MarkdownView value={frame.gradient.message || "No gradient message"} />
            {frame.gradient.target_paths.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {frame.gradient.target_paths.map((path) => (
                  <span
                    key={path}
                    className="rounded border border-border bg-bg-3 px-1.5 py-0.5 font-mono text-[10px]"
                  >
                    {path}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="rounded border border-border bg-bg-2 p-2 text-muted">
            no gradient on this frame
          </div>
        )}
      </div>
    </div>
  );
}

function TracebackValue({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
        {label}
      </div>
      {typeof value === "string" ? (
        <div className="rounded border border-border bg-bg-2 p-2">
          <MarkdownView value={value} />
        </div>
      ) : (
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-border bg-bg-2 p-2 text-[11px] leading-5 text-text">
          {value == null ? "null" : JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  );
}

async function fetchTraceback(runId: string): Promise<TracebackFrame[]> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}/traceback`, {
    headers: { accept: "application/x-ndjson" },
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  const text = await response.text();
  return parseTraceback(text);
}

export function parseTraceback(text: string): TracebackFrame[] {
  const frames: TracebackFrame[] = [];
  for (const item of text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line) as unknown;
      } catch {
        return null;
      }
    })) {
    const parsed = TracebackFrame.safeParse(item);
    if (parsed.success) frames.push(parsed.data);
  }
  return frames;
}

function hasTracebackArtifact(dataSummary: unknown): boolean | null {
  const value = summaryValue(dataSummary, "has_traceback");
  return typeof value === "boolean" ? value : null;
}

function tracebackTitle(dataSummary: unknown): string {
  const path = summaryString(dataSummary, ["traceback_path", "tracebackPath"]);
  const match = path?.match(/epoch_(\d+)_batch_(\d+)\.ndjson$/);
  if (!match) return "PromptTraceback";
  return `PromptTraceback epoch ${match[1]}, batch ${match[2]}`;
}

function summaryString(dataSummary: unknown, keys: string[]): string | null {
  for (const key of keys) {
    const value = summaryValue(dataSummary, key);
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function summaryValue(dataSummary: unknown, key: string): unknown {
  if (!dataSummary || typeof dataSummary !== "object" || Array.isArray(dataSummary)) {
    return undefined;
  }
  return (dataSummary as Record<string, unknown>)[key];
}
