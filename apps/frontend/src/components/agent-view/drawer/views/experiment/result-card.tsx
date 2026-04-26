import type { AgentInvokeResponse } from "@/lib/types";

export interface ExperimentResult {
  id: string;
  startedAt: number;
  input: Record<string, unknown>;
  compare: boolean;
  experiment?: AgentInvokeResponse;
  live?: AgentInvokeResponse;
  error?: string;
}

function fmt(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${Math.round(value)} ms`;
}

function tokens(payload: AgentInvokeResponse | undefined): string {
  if (!payload) return "-";
  const prompt = payload.prompt_tokens ?? 0;
  const completion = payload.completion_tokens ?? 0;
  return `${prompt} / ${completion}`;
}

export function ResultCard({ result }: { result: ExperimentResult }) {
  const experimentOut = result.experiment;
  const liveOut = result.live;
  const sameOutput =
    experimentOut && liveOut
      ? JSON.stringify(experimentOut.response) === JSON.stringify(liveOut.response)
      : null;

  return (
    <div className="space-y-2 rounded border border-border bg-bg-1 p-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span>{new Date(result.startedAt).toLocaleTimeString()}</span>
        {result.error ? <span className="text-err">error</span> : <span className="text-ok">ok</span>}
      </div>

      {result.error ? <div className="text-xs text-err">{result.error}</div> : null}

      {experimentOut ? (
        <div className="rounded border border-border/60 bg-bg-2 p-2 text-[11px]">
          <div className="mb-1 font-semibold text-text">experiment</div>
          <div className="grid grid-cols-2 gap-y-1">
            <span className="text-muted">latency</span>
            <span className="font-mono">{fmt(experimentOut.latency_ms)}</span>
            <span className="text-muted">tokens</span>
            <span className="font-mono">{tokens(experimentOut)}</span>
            <span className="text-muted">hash_content</span>
            <span className="font-mono">{experimentOut.metadata.hash_content}</span>
          </div>
          <pre className="mt-2 max-h-48 overflow-auto rounded border border-border/60 bg-bg-1 p-2 font-mono text-[11px] text-text">
            {JSON.stringify(experimentOut.response, null, 2)}
          </pre>
        </div>
      ) : null}

      {liveOut ? (
        <div className="rounded border border-border/60 bg-bg-2 p-2 text-[11px]">
          <div className="mb-1 font-semibold text-text">live baseline</div>
          <div className="grid grid-cols-2 gap-y-1">
            <span className="text-muted">latency</span>
            <span className="font-mono">{fmt(liveOut.latency_ms)}</span>
            <span className="text-muted">tokens</span>
            <span className="font-mono">{tokens(liveOut)}</span>
            <span className="text-muted">hash_content</span>
            <span className="font-mono">{liveOut.metadata.hash_content}</span>
          </div>
          <pre className="mt-2 max-h-48 overflow-auto rounded border border-border/60 bg-bg-1 p-2 font-mono text-[11px] text-text">
            {JSON.stringify(liveOut.response, null, 2)}
          </pre>
        </div>
      ) : null}

      {result.compare && sameOutput != null ? (
        <div className="text-[11px] text-muted">
          output diff: {sameOutput ? "none (identical)" : "changed"}
        </div>
      ) : null}
    </div>
  );
}
