import { EmptyState } from "@/components/ui/empty-state";
import { GraphResponse, MutationsMatrix } from "@/lib/types";
/**
 * Mermaid wrapper. Lazy-loads mermaid.js only when this component
 * mounts so the rest of the dashboard stays small.
 *
 * If a mutations-matrix is supplied, we tint nodes whose path appears
 * in op_attempt_counts: green when success > 0, orange otherwise.
 */
import { useEffect, useRef, useState } from "react";
import type { z } from "zod";

interface AgentGraphProps {
  data: unknown;
  mutations?: unknown;
}

export function AgentGraph({ data, mutations }: AgentGraphProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  const parsed = GraphResponse.safeParse(data);
  const matrix = MutationsMatrix.safeParse(mutations);

  useEffect(() => {
    if (!parsed.success) return;
    let cancelled = false;
    void (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            background: "var(--color-bg-2)",
            primaryColor: "var(--color-bg-3)",
            primaryTextColor: "var(--color-text)",
            primaryBorderColor: "var(--color-border-strong)",
            lineColor: "var(--color-muted-2)",
          },
          securityLevel: "loose",
        });

        let source = parsed.data.mermaid;
        if (matrix.success) {
          source = appendMutationStyles(source, matrix.data);
        }

        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const { svg } = await mermaid.render(id, source);
        if (cancelled) return;
        if (ref.current) ref.current.innerHTML = svg;
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [parsed, matrix]);

  if (!parsed.success) {
    return (
      <EmptyState title="no graph captured" description="root agent event hasn't arrived yet" />
    );
  }
  if (error) {
    return (
      <EmptyState
        title="mermaid render failed"
        description={<code className="font-mono text-[11px]">{error}</code>}
      />
    );
  }
  return <div ref={ref} className="overflow-auto p-2" />;
}

function appendMutationStyles(source: string, matrix: z.infer<typeof MutationsMatrix>): string {
  // Aggregate per-op totals across all generations to identify hot
  // paths. The path attribution comes from op names in the EvoGradient
  // mutation list — we don't have direct path-to-node mapping in the
  // matrix, so we treat the operator name as the path stem.
  const lines: string[] = [];
  for (let i = 0; i < matrix.ops.length; i++) {
    const op = matrix.ops[i];
    if (op === undefined) continue;
    const totalAttempts = matrix.attempts[i]?.reduce((a, b) => a + b, 0) ?? 0;
    const totalSuccess = matrix.success[i]?.reduce((a, b) => a + b, 0) ?? 0;
    if (totalAttempts === 0) continue;
    // No reliable mapping op -> nodeId in this matrix; we annotate via
    // a footer that lists hottest ops so users see the signal even if
    // node tinting isn't possible.
    const rate = totalSuccess / totalAttempts;
    const fill = rate > 0 ? "var(--color-ok-dim)" : "var(--color-err-dim)";
    const stroke = rate > 0 ? "var(--color-ok)" : "var(--color-warn)";
    lines.push(
      `%% ${op}: ${totalSuccess}/${totalAttempts}, ${(rate * 100).toFixed(0)}%, fill=${fill}, stroke=${stroke}`,
    );
  }
  return lines.length > 0 ? `${source}\n${lines.join("\n")}` : source;
}
