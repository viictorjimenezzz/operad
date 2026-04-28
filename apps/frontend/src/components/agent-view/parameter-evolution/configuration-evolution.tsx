import { EmptyState } from "@/components/ui";
import { cn, truncateMiddle } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { CategoricalEvolution } from "./categorical-evolution";
import { FloatEvolution, type ParameterEvolutionPoint } from "./float-evolution";

export interface ConfigurationEvolutionProps {
  path: string;
  points: ParameterEvolutionPoint[];
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
  compact?: boolean | undefined;
}

type ConfigNode = {
  label: string;
  path: string;
  children: ConfigNode[];
};

export function ConfigurationEvolution({
  path,
  points,
  selectedStep,
  onSelectStep,
  compact,
}: ConfigurationEvolutionProps) {
  const leafPaths = useMemo(() => collectLeafPaths(points.map((point) => point.value)), [points]);
  const tree = useMemo(() => buildTree(leafPaths), [leafPaths]);

  if (points.length === 0) {
    return (
      <EmptyState
        title="no configuration history"
        description="this configuration has no recorded evolution points yet"
      />
    );
  }

  if (leafPaths.length === 0) {
    return (
      <EmptyState
        title="empty configuration"
        description="recorded configuration values do not contain leaf settings"
      />
    );
  }

  return (
    <div className="space-y-1" data-testid="configuration-evolution">
      {tree.children.map((node) => (
        <ConfigRow
          key={node.path}
          node={node}
          rootPath={path}
          points={points}
          selectedStep={selectedStep}
          onSelectStep={onSelectStep}
          compact={compact}
          depth={0}
        />
      ))}
    </div>
  );
}

function ConfigRow({
  node,
  rootPath,
  points,
  selectedStep,
  onSelectStep,
  compact,
  depth,
}: {
  node: ConfigNode;
  rootPath: string;
  points: ParameterEvolutionPoint[];
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
  compact?: boolean | undefined;
  depth: number;
}) {
  const [open, setOpen] = useState(false);
  const leaf = node.children.length === 0;
  const series = leaf ? projectSeries(points, node.path) : [];
  const kind = leaf ? classifySeries(series) : "group";
  const changed = leaf ? hasChanged(series) : true;

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "flex min-h-[var(--row-h)] w-full items-center gap-2 px-2 text-left hover:bg-bg-2/60",
          !changed && leaf && "text-muted-2",
        )}
        style={{ paddingLeft: 8 + depth * 14 }}
      >
        <ChevronRight
          size={13}
          className={cn("shrink-0 text-muted-2 transition-transform", open && "rotate-90")}
        />
        <span className="min-w-0 flex-1 truncate font-mono text-[12px] text-text">
          {node.label}
        </span>
        <span className="shrink-0 text-[11px] text-muted-2">
          {leaf ? `${kind}${changed ? "" : " stable"}` : `${node.children.length} fields`}
        </span>
      </button>
      {open ? (
        <div className="border-t border-border py-2" style={{ paddingLeft: leaf ? 8 : 0 }}>
          {leaf ? (
            <LeafEvolution
              path={`${rootPath}.${node.path}`}
              kind={kind}
              points={series}
              selectedStep={selectedStep}
              onSelectStep={onSelectStep}
              compact={compact}
            />
          ) : (
            <div>
              {node.children.map((child) => (
                <ConfigRow
                  key={child.path}
                  node={child}
                  rootPath={rootPath}
                  points={points}
                  selectedStep={selectedStep}
                  onSelectStep={onSelectStep}
                  compact={compact}
                  depth={depth + 1}
                />
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function LeafEvolution({
  path,
  kind,
  points,
  selectedStep,
  onSelectStep,
  compact,
}: {
  path: string;
  kind: string;
  points: ParameterEvolutionPoint[];
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
  compact?: boolean | undefined;
}) {
  if (kind === "numeric") {
    return (
      <FloatEvolution
        path={path}
        points={points}
        selectedStep={selectedStep}
        onSelectStep={onSelectStep}
        compact={compact}
      />
    );
  }
  return (
    <CategoricalEvolution
      path={path}
      points={points}
      selectedStep={selectedStep}
      onSelectStep={onSelectStep}
      compact={compact}
    />
  );
}

function collectLeafPaths(values: unknown[]): string[] {
  const paths = new Set<string>();
  for (const value of values) collectLeafPath(value, "", paths);
  return [...paths].sort((a, b) => a.localeCompare(b));
}

function collectLeafPath(value: unknown, prefix: string, paths: Set<string>) {
  if (isRecord(value) && Object.keys(value).length > 0) {
    for (const key of Object.keys(value)) {
      collectLeafPath(value[key], prefix ? `${prefix}.${key}` : key, paths);
    }
    return;
  }
  if (prefix) paths.add(prefix);
}

function buildTree(paths: string[]): ConfigNode {
  const root: ConfigNode = { label: "", path: "", children: [] };
  for (const path of paths) {
    let current = root;
    const segments = path.split(".");
    segments.forEach((segment, index) => {
      const nextPath = segments.slice(0, index + 1).join(".");
      let child = current.children.find((item) => item.label === segment);
      if (!child) {
        child = { label: segment, path: nextPath, children: [] };
        current.children.push(child);
      }
      current = child;
    });
  }
  return root;
}

function projectSeries(points: ParameterEvolutionPoint[], path: string): ParameterEvolutionPoint[] {
  return points.map((point) => {
    const value = getPath(point.value, path);
    return {
      ...point,
      value,
      hash: stableHash(value),
    };
  });
}

function getPath(value: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((current, segment) => {
    if (!isRecord(current)) return undefined;
    return current[segment];
  }, value);
}

function classifySeries(points: ParameterEvolutionPoint[]): "numeric" | "categorical" {
  const present = points.map((point) => point.value).filter((value) => value !== undefined);
  if (
    present.length > 0 &&
    present.every((value) => typeof value === "number" && Number.isFinite(value))
  ) {
    return "numeric";
  }
  return "categorical";
}

function hasChanged(points: ParameterEvolutionPoint[]): boolean {
  const first = points[0]?.hash;
  return points.some((point) => point.hash !== first);
}

function stableHash(value: unknown): string {
  return truncateMiddle(JSON.stringify(value) ?? String(value), 16);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
