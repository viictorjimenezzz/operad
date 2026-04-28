import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";
import { ValuePreview } from "@/components/agent-view/compare/value-preview";

export function ParameterDiffSection({ runs }: { runs: CompareRun[] }) {
  const paths = collectPaths(runs);
  const reference = runs[0] ?? null;

  if (paths.length === 0) {
    return (
      <CompareSection title="Parameter Diff">
        <div className="text-[11px] text-muted">no trainable parameters found on compared runs</div>
      </CompareSection>
    );
  }

  return (
    <CompareSection title="Parameter Diff">
      <div
        className="grid"
        style={{ gridTemplateColumns: `220px repeat(${runs.length}, minmax(0, 1fr))` }}
      >
        <div className="border-b border-border px-2 py-1 text-[10px] uppercase tracking-[0.06em] text-muted">
          parameter
        </div>
        {runs.map((run) => (
          <div
            key={run.runId}
            className="border-b border-l border-border px-2 py-1 text-[10px] uppercase tracking-[0.06em] text-muted"
          >
            {run.runId}
          </div>
        ))}
        {paths.map((path) => (
          <ParameterRow key={path} path={path} runs={runs} reference={reference} />
        ))}
      </div>
    </CompareSection>
  );
}

function ParameterRow({
  path,
  runs,
  reference,
}: {
  path: string;
  runs: CompareRun[];
  reference: CompareRun | null;
}) {
  const baseValue = paramFor(reference, path)?.value;
  const baseJson = stable(baseValue);
  return (
    <>
      <div className="border-b border-border px-2 py-1.5">
        <div className="font-mono text-[11px] text-text">{path}</div>
      </div>
      {runs.map((run, index) => {
        const param = paramFor(run, path);
        const changed = index > 0 && stable(param?.value) !== baseJson;
        return (
          <div
            key={`${run.runId}:${path}`}
            className={[
              "border-b border-l border-border px-2 py-1.5",
              changed ? "bg-[--color-warn]/15" : "",
            ].join(" ")}
          >
            <div className="mb-1 text-[10px] text-muted">{param?.type ?? "missing"}</div>
            <ValuePreview value={param?.value ?? null} />
          </div>
        );
      })}
    </>
  );
}

function collectPaths(runs: CompareRun[]): string[] {
  const all = new Set<string>();
  for (const run of runs) {
    for (const param of run.parameters) all.add(param.fullPath);
  }
  return [...all].sort((a, b) => a.localeCompare(b));
}

function paramFor(run: CompareRun | null, path: string) {
  if (!run) return null;
  return run.parameters.find((param) => param.fullPath === path) ?? null;
}

function stable(value: unknown): string {
  if (value == null) return "null";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value) ?? "null";
  } catch {
    return String(value);
  }
}
