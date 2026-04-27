import { HashTag, IconButton, PanelCard, Pill } from "@/components/ui";
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
  flat?: boolean;
}

export function ReproducibilityBlock(props: ReproducibilityBlockProps) {
  const raw = props.dataInvocations ?? props.invocations;
  const parsed = RunInvocationsResponse.safeParse(raw);
  if (!parsed.success) return null;

  const rows = parsed.data.invocations;
  const hashState = useMemo(() => {
    const sets: Record<string, Set<string>> = {};
    const latest = rows[rows.length - 1] ?? null;
    const previous = rows.length >= 2 ? rows[rows.length - 2] : null;
    const changed: Record<string, { current: string | null; previous: string | null }> = {};
    for (const row of rows) {
      for (const { key } of HASH_KEYS) {
        const value = (row as Record<string, unknown>)[key];
        const hash = normalizeHash(value);
        if (!hash) continue;
        if (!sets[key]) sets[key] = new Set();
        sets[key].add(hash);
      }
    }
    for (const { key } of HASH_KEYS) {
      const current = normalizeHash((latest as Record<string, unknown> | null)?.[key]);
      const prev = normalizeHash((previous as Record<string, unknown> | null)?.[key]);
      if (current && prev && current !== prev) changed[key] = { current, previous: prev };
    }
    return { sets, changed };
  }, [rows]);

  const stableCount = HASH_KEYS.filter((h) => (hashState.sets[h.key]?.size ?? 0) === 1).length;
  const totalCount = HASH_KEYS.filter((h) => (hashState.sets[h.key]?.size ?? 0) >= 1).length;
  const drifted = totalCount - stableCount;
  const changedCount = Object.keys(hashState.changed).length;
  const canCompare = rows.length >= 2;

  const titleNode =
    totalCount === 0
      ? "no hashes captured yet"
      : !canCompare
        ? `${totalCount} baseline hash${totalCount === 1 ? "" : "es"}`
        : drifted === 0
          ? `${stableCount}/${totalCount} stable`
          : `${stableCount}/${totalCount} stable · ${drifted} drifted`;

  const title = (
    <span className="flex items-center gap-2">
      {titleNode}
      {changedCount > 0 && canCompare ? (
        <Pill tone="warn" size="sm">
          changed
        </Pill>
      ) : null}
      {changedCount === 0 && canCompare ? (
        <Pill tone="ok" size="sm">
          stable
        </Pill>
      ) : null}
    </span>
  );
  const body =
    totalCount === 0 ? null : (
      <div className="grid gap-1.5">
        {HASH_KEYS.map(({ key, label, help }) => {
          const set = hashState.sets[key];
          const values = set ? [...set] : [];
          const changed = hashState.changed[key];
          const display = changed?.current ?? values[0] ?? null;
          return (
            <HashRow
              key={key}
              label={label}
              help={help}
              hash={display}
              drifted={Boolean(changed)}
              variantCount={values.length}
              {...(changed?.previous ? { previousHash: changed.previous } : {})}
            />
          );
        })}
      </div>
    );

  if (props.flat) return body;

  return (
    <PanelCard eyebrow="Reproducibility" title={title}>
      {body}
    </PanelCard>
  );
}

function normalizeHash(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === "—") return null;
  return trimmed;
}

function HashRow({
  label,
  help,
  hash,
  drifted,
  variantCount,
  previousHash,
}: {
  label: string;
  help: string;
  hash: string | null;
  drifted: boolean;
  variantCount: number;
  previousHash?: string | null | undefined;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div
      className={cn(
        "grid grid-cols-[110px_1fr_auto_auto] items-center gap-3 rounded-md px-2 py-1",
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
        <span
          title={previousHash ? `previous ${previousHash}` : undefined}
          className="rounded-full bg-[--color-warn-dim] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-[--color-warn]"
        >
          changed{variantCount > 1 ? ` · ${variantCount} variants` : ""}
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
