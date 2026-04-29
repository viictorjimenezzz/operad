import { Eyebrow, FieldTree } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface InvocationValueBlockProps {
  label: string;
  data: unknown;
  className?: string;
  bodyClassName?: string;
  defaultDepth?: number;
}

export function InvocationValueBlock({
  label,
  data,
  className,
  bodyClassName,
  defaultDepth = 4,
}: InvocationValueBlockProps) {
  const empty = data === null || data === undefined;

  return (
    <div className={cn("min-w-0", className)}>
      <Eyebrow>{label}</Eyebrow>
      <div
        className={cn(
          "mt-2 flex h-[360px] flex-col rounded-md border border-border bg-bg-2",
          bodyClassName,
        )}
      >
        <div className="min-h-0 flex-1 overflow-auto px-3 py-2">
          {empty ? (
            <div className="text-[12px] text-muted-2">no payload captured</div>
          ) : (
            <FieldTree
              data={data}
              defaultDepth={defaultDepth}
              hideCopy
              truncateStrings={false}
              layout="stacked"
            />
          )}
        </div>
      </div>
    </div>
  );
}

export interface InvocationPromptBlockProps {
  label: string;
  value: string | null;
  meta?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function InvocationPromptBlock({
  label,
  value,
  meta,
  className,
  bodyClassName,
}: InvocationPromptBlockProps) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-center gap-2">
        <Eyebrow>{label}</Eyebrow>
        {meta}
      </div>
      <pre
        className={cn(
          "mt-2 max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-bg-inset p-3 font-mono text-[11px] leading-5 text-text",
          bodyClassName,
        )}
      >
        {value?.trim() ? value : "—"}
      </pre>
    </div>
  );
}
