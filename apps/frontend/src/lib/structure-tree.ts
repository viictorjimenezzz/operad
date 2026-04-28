import type { AgentFlowNode, AgentGraphResponse, AgentParametersResponse } from "@/lib/types";

export type ParameterDescriptor = {
  path: string;
  fullPath: string;
  type: "text" | "rule_list" | "example_list" | "float" | "categorical" | "configuration";
  requiresGrad: boolean;
  currentValue: unknown;
  currentHash: string;
};

export type StructureTreeNode = {
  path: string;
  label: string;
  className: string;
  kind: "composite" | "leaf";
  hashContent: string | null;
  children: StructureTreeNode[];
  parameters: ParameterDescriptor[];
};

type RawParameter = AgentParametersResponse["parameters"][number] & {
  hash?: unknown;
};

const DECLARED_PARAMETER_PATHS = ["role", "task", "rules", "examples"] as const;
const CATEGORICAL_CONFIG_KEYS = new Set(["backend", "model", "renderer"]);

export function buildStructureTree(
  graph: AgentGraphResponse,
  params: AgentParametersResponse[],
): StructureTreeNode {
  const nodes = graph.nodes;
  const rootPath = graph.root ?? nodes.find((node) => node.parent_path == null)?.path ?? "";
  const rootNode = nodes.find((node) => node.path === rootPath) ?? nodes[0];
  const paramsByPath = new Map(
    params.map((response) => [response.agent_path, response.parameters]),
  );
  const childrenByParent = new Map<string, AgentFlowNode[]>();

  for (const node of nodes) {
    if (!node.parent_path) continue;
    const children = childrenByParent.get(node.parent_path) ?? [];
    children.push(node);
    childrenByParent.set(node.parent_path, children);
  }

  if (!rootNode) {
    return {
      path: rootPath,
      label: labelForPath(rootPath),
      className: labelForPath(rootPath) || "Agent",
      kind: "leaf",
      hashContent: null,
      children: [],
      parameters: buildParameters(rootPath, []),
    };
  }

  function visit(node: AgentFlowNode): StructureTreeNode {
    const children = childrenByParent.get(node.path) ?? [];
    const kind = children.length > 0 ? "composite" : "leaf";
    return {
      path: node.path,
      label: labelForPath(node.path),
      className: node.class_name || labelForPath(node.path) || "Agent",
      kind,
      hashContent: hashContentFor(node),
      children: children.map(visit),
      parameters:
        kind === "leaf" ? buildParameters(node.path, paramsByPath.get(node.path) ?? []) : [],
    };
  }

  return visit(rootNode);
}

function buildParameters(nodePath: string, rawParams: RawParameter[]): ParameterDescriptor[] {
  const byPath = new Map(rawParams.map((param) => [param.path, param]));
  const out: ParameterDescriptor[] = DECLARED_PARAMETER_PATHS.map((path) =>
    descriptorFor(nodePath, path, byPath.get(path), null),
  );
  const seen = new Set(out.map((param) => param.path));

  for (const param of rawParams) {
    if (seen.has(param.path)) continue;
    if (param.path === "config" && isRecord(param.value)) {
      for (const [path, value] of flattenConfig(param.value)) {
        out.push(descriptorFor(nodePath, path, param, value, true));
        seen.add(path);
      }
      continue;
    }
    out.push(descriptorFor(nodePath, param.path, param, param.value));
    seen.add(param.path);
  }

  return out;
}

function descriptorFor(
  nodePath: string,
  path: string,
  param: RawParameter | undefined,
  fallbackValue: unknown,
  useFallback = false,
): ParameterDescriptor {
  const currentValue = useFallback || !param ? fallbackValue : param.value;
  return {
    path,
    fullPath: `${nodePath}.${path}`,
    type: inferParameterType(path, currentValue),
    requiresGrad: param?.requires_grad ?? false,
    currentValue,
    currentHash: typeof param?.hash === "string" ? param.hash : stableHash(currentValue),
  };
}

function inferParameterType(path: string, value: unknown): ParameterDescriptor["type"] {
  if (path === "role" || path === "task") return "text";
  if (path === "rules") return "rule_list";
  if (path === "examples") return "example_list";
  if (path === "config") return "configuration";
  if (!path.startsWith("config.")) return "configuration";
  if (typeof value === "number") return "float";
  const key = path.split(".").at(-1) ?? "";
  if (CATEGORICAL_CONFIG_KEYS.has(key)) return "categorical";
  return "configuration";
}

function flattenConfig(
  value: Record<string, unknown>,
  prefix = "config",
): Array<[string, unknown]> {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = `${prefix}.${key}`;
    if (isRecord(child)) return flattenConfig(child, path);
    return [[path, child]];
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function labelForPath(path: string): string {
  return path.split(".").at(-1) ?? path;
}

function hashContentFor(node: AgentFlowNode): string | null {
  const hash = (node as AgentFlowNode & { hash_content?: unknown }).hash_content;
  return typeof hash === "string" && hash.length > 0 ? hash : null;
}

function stableHash(value: unknown): string {
  const text = JSON.stringify(value);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(16).padStart(8, "0").slice(0, 16);
}
