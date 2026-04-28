import { CollapsibleSection, EmptyState, MarkdownView, Pill } from "@/components/ui";
import { useManifest } from "@/hooks/use-runs";
import { langfuseUrlFor } from "@/lib/langfuse";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

export interface PromptTracebackReaderProps {
  runId: string;
}

const CriticSchema = z.object({
  run_id: z.string().optional(),
  runId: z.string().optional(),
  langfuse_url: z.string().nullable().optional(),
  langfuseUrl: z.string().nullable().optional(),
});

const GradientSchema = z.object({
  message: z.string().default(""),
  severity: z.union([z.string(), z.number()]).optional(),
  optimizer: z.string().optional(),
  optimizer_step: z.number().optional(),
  optimizerStep: z.number().optional(),
  critic: CriticSchema.nullable().optional(),
});

const TracebackFrameSchema = z.object({
  agent_path: z.string(),
  input: z.unknown().nullable().optional(),
  output: z.unknown().nullable().optional(),
  rendered_prompt: z.unknown().nullable().optional(),
  optimizer: z.string().optional(),
  optimizer_step: z.number().optional(),
  optimizerStep: z.number().optional(),
  gradient: GradientSchema.nullable().optional(),
});

const TracebackResponseSchema = z.object({
  frames: z.array(TracebackFrameSchema).default([]),
});

type TracebackFrame = z.infer<typeof TracebackFrameSchema>;

export function PromptTracebackReader({ runId }: PromptTracebackReaderProps) {
  const manifest = useManifest();
  const query = useQuery({
    queryKey: ["traceback", runId] as const,
    queryFn: () => fetchTraceback(runId),
    enabled: Boolean(runId),
    retry: false,
  });

  if (query.isLoading) {
    return <div className="text-xs text-muted">loading traceback...</div>;
  }

  if (query.error instanceof TracebackNotFoundError) {
    return (
      <EmptyState
        title="no traceback recorded"
        description="this run did not save a PromptTraceback; add ptb.PromptTraceback.from_run(...).save(path) to your training script"
      />
    );
  }

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

  const langfuseBase = manifest.data?.langfuseUrl ?? null;
  return (
    <div className="space-y-3">
      {frames.map((frame, index) => (
        <FrameCard
          key={`${frame.agent_path}-${index}`}
          frame={frame}
          order={frames.length - index}
          index={index}
          langfuseBase={langfuseBase}
        />
      ))}
    </div>
  );
}

function FrameCard({
  frame,
  order,
  index,
  langfuseBase,
}: {
  frame: TracebackFrame;
  order: number;
  index: number;
  langfuseBase: string | null;
}) {
  const severity = severityLabel(frame.gradient?.severity);
  const optimizer = optimizerName(frame);
  const step = optimizerStep(frame);
  const langfuseHref = resolveLangfuseHref(frame, langfuseBase);

  return (
    <section className="space-y-3 rounded-lg border border-border bg-bg-1 p-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
          frame #{order}
        </span>
        <Pill tone={severityPillTone(severity)}>{severity}</Pill>
      </div>

      <div className="space-y-1 text-xs">
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-muted">agent:</span>
          <span className="font-mono text-text">{frame.agent_path}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <span className="text-muted">optimizer:</span>
          <span className="text-text">{optimizer}</span>
          <span className="text-muted">·</span>
          <span className="text-text">step {step}</span>
        </div>
      </div>

      <div className="rounded border border-border bg-bg-2 p-2">
        <MarkdownView value={frame.gradient?.message || "No gradient message."} />
      </div>

      <CollapsibleSection
        id={`traceback-frame-${index}`}
        label="expand prompt + i/o"
        preview={<span className="font-mono text-[11px]">prompt · input · output</span>}
      >
        <div className="space-y-3">
          <TracebackValue label="prompt" value={frame.rendered_prompt} />
          <TracebackValue label="input" value={frame.input} />
          <TracebackValue label="output" value={frame.output} />
        </div>
      </CollapsibleSection>

      {langfuseHref ? (
        <a
          href={langfuseHref}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex text-xs text-accent underline-offset-2 hover:underline"
        >
          langfuse -&gt;
        </a>
      ) : null}
    </section>
  );
}

function TracebackValue({ label, value }: { label: string; value: unknown }) {
  return (
    <section className="space-y-1">
      <div className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className="rounded border border-border bg-bg-2 p-2">
        <MarkdownView value={toMarkdown(value)} />
      </div>
    </section>
  );
}

class TracebackNotFoundError extends Error {
  constructor() {
    super("traceback not found");
    this.name = "TracebackNotFoundError";
  }
}

async function fetchTraceback(runId: string): Promise<TracebackFrame[]> {
  const response = await fetch(`/runs/${encodeURIComponent(runId)}/traceback.ndjson`, {
    headers: { accept: "application/json" },
  });
  if (response.status === 404) throw new TracebackNotFoundError();
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);

  const raw: unknown = await response.json();
  const parsed = TracebackResponseSchema.safeParse(raw);
  if (!parsed.success) throw new Error("invalid traceback response");
  return parsed.data.frames;
}

function optimizerName(frame: TracebackFrame): string {
  return frame.gradient?.optimizer ?? frame.optimizer ?? "unknown";
}

function optimizerStep(frame: TracebackFrame): number | string {
  return (
    frame.gradient?.optimizer_step ??
    frame.gradient?.optimizerStep ??
    frame.optimizer_step ??
    frame.optimizerStep ??
    "-"
  );
}

function severityLabel(raw: string | number | undefined): "low" | "medium" | "high" {
  if (typeof raw === "string") {
    const value = raw.toLowerCase().trim();
    if (value === "low" || value === "medium" || value === "high") return value;
    return "low";
  }
  if (typeof raw === "number") {
    if (raw < 0.34) return "low";
    if (raw < 0.67) return "medium";
    return "high";
  }
  return "low";
}

function severityPillTone(severity: "low" | "medium" | "high"): "ok" | "warn" | "error" {
  if (severity === "high") return "error";
  if (severity === "medium") return "warn";
  return "ok";
}

function resolveLangfuseHref(frame: TracebackFrame, baseUrl: string | null): string | null {
  const direct = frame.gradient?.critic?.langfuseUrl ?? frame.gradient?.critic?.langfuse_url ?? null;
  if (typeof direct === "string" && direct.length > 0) return direct;
  const runId = frame.gradient?.critic?.runId ?? frame.gradient?.critic?.run_id ?? null;
  if (!baseUrl || !runId) return null;
  return langfuseUrlFor(baseUrl, runId);
}

function toMarkdown(value: unknown): string {
  if (value == null) return "not recorded";
  if (typeof value === "string") return value;
  return `\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
}

