import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
  cell: (row: T) => ReactNode;
  mono?: boolean;
}

export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  density?: "default" | "compact";
  onRowClick?: (row: T) => void;
  expandable?: (row: T) => ReactNode;
  empty?: ReactNode;
  className?: string;
}

export function Table<T>({
  columns,
  rows,
  rowKey,
  density = "default",
  onRowClick,
  expandable,
  empty,
  className,
}: TableProps<T>) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const rowHeight = density === "compact" ? "h-[22px]" : "h-7";
  const gridTemplate = columns
    .map((c) => c.width ?? `minmax(0, 1fr)`)
    .join(" ");

  if (rows.length === 0) {
    return (
      <div className={cn("rounded-lg border border-border bg-bg-1", className)}>
        <div className="px-3 py-4 text-center text-[12px] text-muted-2">
          {empty ?? "no rows"}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-bg-1",
        className,
      )}
    >
      <div
        role="row"
        className={cn(
          "grid items-center gap-3 border-b border-border bg-bg-2/40 px-3",
          rowHeight,
        )}
        style={{ gridTemplateColumns: expandable ? `${gridTemplate} 16px` : gridTemplate }}
      >
        {columns.map((col) => (
          <div
            key={col.key}
            className={cn(
              "text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2",
              col.align === "right" && "text-right",
              col.align === "center" && "text-center",
            )}
          >
            {col.header}
          </div>
        ))}
        {expandable ? <span /> : null}
      </div>
      <div role="rowgroup">
        {rows.map((row) => {
          const id = rowKey(row);
          const isExpanded = expandedId === id;
          return (
            <div key={id} className="border-b border-border last:border-b-0">
              <div
                role="row"
                className={cn(
                  "grid items-center gap-3 px-3 text-[12px] transition-colors",
                  rowHeight,
                  (onRowClick || expandable) &&
                    "cursor-pointer hover:bg-bg-2/40",
                  isExpanded && "bg-bg-2/60",
                )}
                style={{
                  gridTemplateColumns: expandable ? `${gridTemplate} 16px` : gridTemplate,
                }}
                onClick={() => {
                  if (expandable) {
                    setExpandedId((curr) => (curr === id ? null : id));
                  }
                  onRowClick?.(row);
                }}
              >
                {columns.map((col) => (
                  <div
                    key={col.key}
                    className={cn(
                      "min-w-0 truncate",
                      col.mono && "font-mono tabular-nums",
                      col.align === "right" && "text-right",
                      col.align === "center" && "text-center",
                    )}
                  >
                    {col.cell(row)}
                  </div>
                ))}
                {expandable ? (
                  <ChevronDown
                    size={12}
                    className={cn(
                      "text-muted-2 transition-transform",
                      isExpanded && "rotate-180",
                    )}
                  />
                ) : null}
              </div>
              <AnimatePresence initial={false}>
                {isExpanded && expandable ? (
                  <motion.div
                    key="body"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.16, ease: [0.2, 0.8, 0.2, 1] }}
                    className="overflow-hidden"
                  >
                    <div className="border-t border-border bg-bg-1 px-3 py-2">
                      {expandable(row)}
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
