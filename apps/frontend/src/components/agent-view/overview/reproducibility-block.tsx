import { HashTag, IconButton, Section } from "@/components/ui";
import { RunInvocationsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";

const HASH_KEYS = [
  { key: "hash_content", label: "content", help: "agent's declared state" },
  { key: "hash_model", label: "model", help: "backend + model + sampling" },
  { key: "hash_prompt", label: "prompt", help: "rendered system + user message" },
  { key: "hash_input", label: "input", help: "canonical JSON dump of input" },
  { key: "hash_output_schema", label: "output schema", help: "target Pydantic class" },
  { key: "hash_graph", label: "graph", help: "AgentGraph topology" },
  { key: "hash_config", label: "config", help: "Configuration (key redacted)" },
] as const;

export interface ReproducibilityBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
}

export function ReproducibilityBlock(props: ReproducibilityBlockProps) {
  const raw = props.dataInvocations ?? props.invocations;
  const parsed = RunInvocationsResponse.safeParse(raw);
  if (!parsed.success) return null;

  const rows = parsed.data.invocations;
  const hashSets = useMemo(() => {
    const acc: Record<string, Set<string>> = {};
    for (const row of rows) {
      for (const { key } of HASH_KEYS) {
        const value = (row as Record<string, unknown>)[key];
        if (typeof value !== "string") continue;
        if (!acc[key]) acc[key] = new Set();
        acc[key].add(value);
      }
    }
    return acc;
  }, [rows]);

  const stableCount = HASH_KEYS.filter((h) => (hashSets[h.key]?.size ?? 0) === 1).length;
  const totalCount = HASH_KEYS.filter((h) => (hashSets[h.key]?.size ?? 0) >= 1).length;

  const summary =
    totalCount === 0
      ? "no hashes captured yet"
      : stableCount === totalCount
        ? `${stableCount}/${totalCount} hashes stable across ${rows.length} invocation${rows.length === 1 ? "" : "s"}`
        : `${stableCount}/${totalCount} stable · ${totalCount - stableCount} drifted`;

  return (
    <Section title="Reproducibility" summary={summary} disabled={totalCount === 0}>
      <div className="grid gap-1.5">
        {HASH_KEYS.map(({ key, label, help }) => {
          const set = hashSets[key];
          const values = set ? [...set] : [];
          const drifted = values.length > 1;
          const display = values[0] ?? null;
          return (
            <HashRow
              key={key}
              label={label}
              help={help}
              hash={display}
              drifted={drifted}
              variantCount={values.length}
            />
          );
        })}
      </div>
    </Section>
  );
}

function HashRow({
  label,
  help,
  hash,
  drifted,
  variantCount,
}: {
  label: string;
  help: string;
  hash: string | null;
  drifted: boolean;
  variantCount: number;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div
      className={cn(
        "grid grid-cols-[110px_1fr_auto_auto] items-center gap-3 rounded-lg px-3 py-1.5",
        drifted ? "bg-[--color-warn-dim]/40" : "",
      )}
    >
      <div className="flex flex-col">
        <span className="text-[12px] text-text">{label}</span>
        <span className="text-[10px] text-muted-2">{help}</span>
      </div>
      <div className="min-w-0">
        {hash ? (
          <HashTag hash={hash} mono size="sm" />
        ) : (
          <span className="text-[12px] text-muted-2">—</span>
        )}
      </div>
      {drifted ? (
        <span className="rounded-full bg-[--color-warn-dim] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-[--color-warn]">
          {variantCount} variants
        </span>
      ) : (
        <span />
      )}
      <IconButton
        size="sm"
        aria-label={`copy ${label} hash`}
        disabled={!hash}
        onClick={() => {
          if (!hash) return;
          navigator.clipboard.writeText(hash).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 900);
          });
        }}
      >
        {copied ? <Check size={12} className="text-[--color-ok]" /> : <Copy size={12} />}
      </IconButton>
    </div>
  );
}
