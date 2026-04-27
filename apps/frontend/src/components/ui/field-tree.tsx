import { cn } from "@/lib/utils";
import { Check, ChevronRight, Copy } from "lucide-react";
import { type ReactNode, useState } from "react";

export interface FieldTreeProps {
  data: unknown;
  /** Default expansion depth — 0 means everything collapsed under root (we still show top-level keys). */
  defaultDepth?: number;
  className?: string;
  /** Hide the copy buttons (compact contexts). */
  hideCopy?: boolean;
  /** Render as a single-line preview when at the very top (used in collapsed cards). */
  preview?: boolean;
  /** Optional descriptions keyed by field path (dotted). */
  descriptions?: Record<string, string>;
  /** Full inspectors can disable string truncation while compact previews keep it on. */
  truncateStrings?: boolean;
}

type NodeProps = {
  label: ReactNode;
  value: unknown;
  depth: number;
  defaultDepth: number;
  path: string;
  hideCopy: boolean;
  descriptions?: Record<string, string> | undefined;
  truncateStrings: boolean;
};

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function valueLabel(v: unknown, truncateStrings = true): string {
  if (v === null) return "null";
  if (v === undefined) return "undefined";
  if (typeof v === "string") {
    const s = truncateStrings && v.length > 80 ? `${v.slice(0, 80)}…` : v;
    return JSON.stringify(s);
  }
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return `[${v.length}]`;
  if (isObj(v)) return `{${Object.keys(v).length}}`;
  return String(v);
}

function CopyButton({ value }: { value: unknown }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label="copy value"
      className="ml-1 rounded p-0.5 text-muted-2 opacity-0 transition-opacity hover:text-text group-hover:opacity-100"
      onClick={(e) => {
        e.stopPropagation();
        const out = typeof value === "string" ? value : JSON.stringify(value, null, 2);
        navigator.clipboard.writeText(out).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 900);
        });
      }}
    >
      {copied ? <Check size={11} className="text-[--color-ok]" /> : <Copy size={11} />}
    </button>
  );
}

function Node({
  label,
  value,
  depth,
  defaultDepth,
  path,
  hideCopy,
  descriptions,
  truncateStrings,
}: NodeProps) {
  const isContainer = isObj(value) || Array.isArray(value);
  const [open, setOpen] = useState(depth < defaultDepth);
  const desc = descriptions?.[path];

  if (!isContainer) {
    const valueClass =
      typeof value === "string"
        ? "text-[--color-ok]"
        : typeof value === "number"
          ? "text-[--color-accent]"
          : typeof value === "boolean"
            ? "text-[--color-warn]"
            : "text-muted-2";
    return (
      <div className="group flex items-baseline gap-2 py-0.5 font-mono text-[12px]">
        <span className="flex-shrink-0 text-muted">{label}:</span>
        <span className={cn("min-w-0 break-all", valueClass)}>
          {valueLabel(value, truncateStrings)}
        </span>
        {hideCopy ? null : <CopyButton value={value} />}
        {desc ? <span className="ml-2 truncate text-[11px] text-muted-2">— {desc}</span> : null}
      </div>
    );
  }

  return (
    <div className="font-mono text-[12px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-1.5 py-0.5 text-muted hover:text-text"
      >
        <ChevronRight
          size={11}
          className={cn(
            "flex-shrink-0 text-muted-2 transition-transform duration-150",
            open && "rotate-90",
          )}
        />
        <span className="text-muted">{label}</span>
        <span className="text-muted-2">{valueLabel(value, truncateStrings)}</span>
        {hideCopy ? null : <CopyButton value={value} />}
      </button>
      {open ? (
        <div className="ml-3 border-l border-border pl-2">
          {Array.isArray(value)
            ? value.map((v, i) => (
                <Node
                  key={i}
                  label={i.toString()}
                  value={v}
                  depth={depth + 1}
                  defaultDepth={defaultDepth}
                  path={`${path}[${i}]`}
                  hideCopy={hideCopy}
                  descriptions={descriptions}
                  truncateStrings={truncateStrings}
                />
              ))
            : Object.entries(value as Record<string, unknown>).map(([k, v]) => (
                <Node
                  key={k}
                  label={k}
                  value={v}
                  depth={depth + 1}
                  defaultDepth={defaultDepth}
                  path={path ? `${path}.${k}` : k}
                  hideCopy={hideCopy}
                  descriptions={descriptions}
                  truncateStrings={truncateStrings}
                />
              ))}
        </div>
      ) : null}
    </div>
  );
}

export function FieldTree({
  data,
  defaultDepth = 1,
  className,
  hideCopy = false,
  preview = false,
  descriptions,
  truncateStrings = true,
}: FieldTreeProps) {
  if (data === null || data === undefined) {
    return <span className="text-[12px] text-muted-2">—</span>;
  }
  if (preview && isObj(data)) {
    const entries = Object.entries(data).slice(0, 3);
    if (entries.length === 0) return <span className="text-[12px] text-muted-2">empty</span>;
    return (
      <div className={cn("space-y-0.5", className)}>
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-2 truncate font-mono text-[12px]">
            <span className="flex-shrink-0 text-muted">{k}:</span>
            <span className="min-w-0 truncate text-text">{valueLabel(v)}</span>
          </div>
        ))}
        {Object.keys(data).length > 3 ? (
          <div className="text-[11px] text-muted-2">
            +{Object.keys(data).length - 3} more fields
          </div>
        ) : null}
      </div>
    );
  }
  if (isObj(data) || Array.isArray(data)) {
    return (
      <div className={cn("space-y-0.5", className)}>
        {Array.isArray(data)
          ? data.map((v, i) => (
              <Node
                key={i}
                label={i.toString()}
                value={v}
                depth={0}
                defaultDepth={defaultDepth}
                path={`[${i}]`}
                hideCopy={hideCopy}
                descriptions={descriptions}
                truncateStrings={truncateStrings}
              />
            ))
          : Object.entries(data as Record<string, unknown>).map(([k, v]) => (
              <Node
                key={k}
                label={k}
                value={v}
                depth={0}
                defaultDepth={defaultDepth}
                path={k}
                hideCopy={hideCopy}
                descriptions={descriptions}
                truncateStrings={truncateStrings}
              />
            ))}
      </div>
    );
  }
  return (
    <span className="font-mono text-[12px] text-text">{valueLabel(data, truncateStrings)}</span>
  );
}
