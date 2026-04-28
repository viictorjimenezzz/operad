import { hashColor, paletteIndex } from "@/lib/hash-color";
import type { ParameterDescriptor, StructureTreeNode } from "@/lib/structure-tree";
import { cn } from "@/lib/utils";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ChevronDown,
  ChevronRight,
  CornerDownRight,
  FileText,
  Settings,
  SlidersHorizontal,
} from "lucide-react";
import {
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface StructureTreeProps {
  root: StructureTreeNode;
  selectedParamPath?: string | null;
  onSelectParameter?: (param: ParameterDescriptor, node: StructureTreeNode) => void;
  onSelectAgent?: (node: StructureTreeNode) => void;
  density?: "compact" | "comfortable";
}

type FlatRow =
  | { id: string; type: "node"; node: StructureTreeNode; depth: number }
  | {
      id: string;
      type: "param";
      node: StructureTreeNode;
      param: ParameterDescriptor;
      depth: number;
    };

const ROW_HEIGHT = 28;
const ROW_HEIGHT_COMFORTABLE = 34;
const VIRTUALIZE_AFTER = 200;

export function StructureTree({
  root,
  selectedParamPath = null,
  onSelectParameter,
  onSelectAgent,
  density = "compact",
}: StructureTreeProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(() => defaultExpanded(root));
  const [activeIndex, setActiveIndex] = useState(0);
  const rowHeight = density === "comfortable" ? ROW_HEIGHT_COMFORTABLE : ROW_HEIGHT;

  const flat = useMemo(() => flattenTree(root, expanded), [root, expanded]);
  const shouldVirtualize = useMemo(
    () => countLeaves(root) > 50 || flat.length > VIRTUALIZE_AFTER,
    [root, flat.length],
  );
  const selectedIndex = flat.findIndex(
    (row) => row.type === "param" && row.param.fullPath === selectedParamPath,
  );
  const focusedIndex = selectedIndex >= 0 ? selectedIndex : activeIndex;

  const virtualizer = useVirtualizer({
    count: flat.length,
    getScrollElement: () => viewportRef.current,
    estimateSize: () => rowHeight,
    overscan: 12,
    enabled: shouldVirtualize,
  });
  const virtualItems = virtualizer.getVirtualItems();
  const rowsToRender =
    shouldVirtualize && virtualItems.length > 0
      ? virtualItems.map((item) => ({
          index: item.index,
          key: item.key,
          start: item.start,
          size: item.size,
        }))
      : flat.map((_, index) => ({
          index,
          key: flat[index]?.id ?? index,
          start: index * rowHeight,
          size: rowHeight,
        }));

  useEffect(() => {
    setActiveIndex((current) => Math.min(current, Math.max(flat.length - 1, 0)));
  }, [flat.length]);

  const toggle = (path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const activate = (index: number) => {
    const next = Math.max(0, Math.min(index, flat.length - 1));
    setActiveIndex(next);
    if (shouldVirtualize) {
      virtualizer.scrollToIndex(next, { align: "auto" });
    }
  };

  const selectRow = (row: FlatRow) => {
    if (row.type === "node") {
      if (row.node.kind === "leaf") toggle(row.node.path);
      onSelectAgent?.(row.node);
      return;
    }
    if (row.param.requiresGrad) {
      onSelectParameter?.(row.param, row.node);
    } else {
      toggle(row.id);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (flat.length === 0) return;
    const row = flat[activeIndex];
    if (!row) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      activate(activeIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activate(activeIndex - 1);
    } else if (event.key === "ArrowRight") {
      if (row.type === "node" && !expanded.has(row.node.path)) {
        event.preventDefault();
        toggle(row.node.path);
      }
    } else if (event.key === "ArrowLeft") {
      if (row.type === "node" && expanded.has(row.node.path)) {
        event.preventDefault();
        toggle(row.node.path);
      }
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectRow(row);
    }
  };

  return (
    <div
      ref={viewportRef}
      role="tree"
      // biome-ignore lint/a11y/noNoninteractiveTabindex: The ARIA tree container owns arrow-key navigation.
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="max-h-full overflow-auto border-y border-border text-[12px] outline-none focus-visible:ring-1 focus-visible:ring-accent"
      aria-label="agent structure"
    >
      <div
        className="relative"
        style={{ height: shouldVirtualize ? virtualizer.getTotalSize() : undefined }}
      >
        {rowsToRender.map(({ index, key, start, size }) => {
          const row = flat[index];
          if (!row) return null;
          const style: CSSProperties = shouldVirtualize
            ? { height: size, transform: `translateY(${start}px)` }
            : { height: size };
          return (
            <div
              key={key}
              className={cn(shouldVirtualize && "absolute left-0 top-0 w-full")}
              style={style}
            >
              {row.type === "node" ? (
                <NodeRow
                  row={row}
                  expanded={expanded.has(row.node.path)}
                  active={index === focusedIndex}
                  onToggle={() => toggle(row.node.path)}
                  onSelect={() => {
                    activate(index);
                    selectRow(row);
                  }}
                />
              ) : (
                <ParameterRow
                  row={row}
                  active={index === focusedIndex}
                  selected={row.param.fullPath === selectedParamPath}
                  expanded={expanded.has(row.id)}
                  onSelect={() => {
                    activate(index);
                    selectRow(row);
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function NodeRow({
  row,
  expanded,
  active,
  onToggle,
  onSelect,
}: {
  row: Extract<FlatRow, { type: "node" }>;
  expanded: boolean;
  active: boolean;
  onToggle: () => void;
  onSelect: () => void;
}) {
  const { node, depth } = row;
  const isComposite = node.kind === "composite";
  const classColor = `var(--qual-${paletteIndex(node.className) + 1})`;
  const hasTrainable = node.parameters.some((param) => param.requiresGrad);

  return (
    <div
      role="treeitem"
      aria-expanded={isComposite || node.parameters.length > 0 ? expanded : undefined}
      className={rowClass(active)}
      style={{ paddingLeft: 8 + depth * 16 }}
    >
      {isComposite ? (
        <button
          type="button"
          aria-label={expanded ? "collapse composite" : "expand composite"}
          aria-expanded={expanded}
          onClick={onToggle}
          className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-muted-2 hover:text-text"
        >
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
      ) : (
        <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: hashColor(node.hashContent) }}
          />
        </span>
      )}
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        {isComposite ? (
          <span
            aria-hidden
            className="h-2 w-2 flex-shrink-0 rounded-[2px]"
            style={{ background: classColor }}
          />
        ) : null}
        <span className="min-w-0 truncate font-medium text-text">{node.className}</span>
        {node.label !== node.className ? (
          <span className="min-w-0 truncate text-muted-2">{node.label}</span>
        ) : null}
        {isComposite ? (
          <span className="ml-auto flex-shrink-0 rounded-full bg-bg-3 px-1.5 text-[10px] tabular-nums text-muted-2">
            {node.children.length}
          </span>
        ) : hasTrainable ? (
          <Settings
            aria-label="trainable parameters"
            size={13}
            className="ml-auto flex-shrink-0 text-accent"
          />
        ) : null}
      </button>
    </div>
  );
}

function ParameterRow({
  row,
  active,
  selected,
  expanded,
  onSelect,
}: {
  row: Extract<FlatRow, { type: "param" }>;
  active: boolean;
  selected: boolean;
  expanded: boolean;
  onSelect: () => void;
}) {
  const { param, depth } = row;
  const trainable = param.requiresGrad;
  return (
    <div
      role="treeitem"
      aria-selected={selected}
      className={rowClass(active || selected)}
      style={{ paddingLeft: 8 + depth * 16 }}
    >
      <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center text-muted-2">
        {trainable ? (
          <ChevronRight size={12} />
        ) : expanded ? (
          <ChevronDown size={12} />
        ) : (
          <FileText size={12} />
        )}
      </span>
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2 text-left",
          trainable ? "text-accent" : "text-muted",
        )}
      >
        {iconForParameter(param)}
        <span className="min-w-0 truncate font-mono text-[11px]">{param.path}</span>
        <span className="ml-auto min-w-0 truncate text-[11px] text-muted-2">
          {trainable || expanded ? formatValue(param.currentValue) : "view value"}
        </span>
      </button>
    </div>
  );
}

function iconForParameter(param: ParameterDescriptor): ReactNode {
  if (param.type === "configuration" || param.type === "float" || param.type === "categorical") {
    return <SlidersHorizontal size={12} className="flex-shrink-0" />;
  }
  return <CornerDownRight size={12} className="flex-shrink-0" />;
}

function flattenTree(root: StructureTreeNode, expanded: Set<string>): FlatRow[] {
  const rows: FlatRow[] = [];
  function visit(node: StructureTreeNode, depth: number) {
    rows.push({ id: node.path, type: "node", node, depth });
    if (!expanded.has(node.path)) return;
    if (node.kind === "leaf") {
      for (const param of node.parameters) {
        rows.push({
          id: `${node.path}::${param.path}`,
          type: "param",
          node,
          param,
          depth: depth + 1,
        });
      }
      return;
    }
    for (const child of node.children) visit(child, depth + 1);
  }
  visit(root, 0);
  return rows;
}

function defaultExpanded(root: StructureTreeNode): Set<string> {
  const out = new Set<string>();
  function visit(node: StructureTreeNode) {
    if (node.kind === "composite" && node.children.length <= 5) {
      out.add(node.path);
      node.children.forEach(visit);
    }
  }
  visit(root);
  return out;
}

function countLeaves(root: StructureTreeNode): number {
  if (root.kind === "leaf") return 1;
  return root.children.reduce((sum, child) => sum + countLeaves(child), 0);
}

function rowClass(active: boolean): string {
  return cn(
    "flex w-full items-center gap-1.5 border-b border-border/70 pr-2 transition-colors hover:bg-bg-2/60",
    active && "bg-bg-2",
  );
}

function formatValue(value: unknown): string {
  if (value == null) return "unset";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `${value.length} items`;
  return "object";
}
