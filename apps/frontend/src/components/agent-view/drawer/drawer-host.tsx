import {
  type DrawerViewProps,
  ensureDefaultDrawerViews,
  getDrawerView,
} from "@/components/agent-view/drawer/drawer-registry";
import { StubView } from "@/components/agent-view/drawer/views/_stub";
import type { DrawerKind, DrawerPayload } from "@/stores";
import type { ReactElement } from "react";

interface DrawerHostProps {
  runId: string;
  kind: DrawerKind;
  payload: DrawerPayload;
}

export function drawerTitle(kind: DrawerKind, payload: DrawerPayload): string {
  if (!kind) return "";
  switch (kind) {
    case "langfuse":
      return `langfuse trace${payload.agentPath ? ` · ${payload.agentPath}` : ""}`;
    case "events":
      return `filtered events${payload.agentPath ? ` · ${payload.agentPath}` : ""}`;
    case "prompts":
      return `prompt diff${payload.agentPath ? ` · ${payload.agentPath}` : ""}`;
    case "values":
      return `values${payload.attr ? ` · ${String(payload.attr)}` : ""}`;
    default:
      return kind;
  }
}

export function DrawerHost({ runId, kind, payload }: DrawerHostProps) {
  ensureDefaultDrawerViews();
  const view = getDrawerView(kind);
  const View = (view?.component ?? StubView) as unknown as (
    props: DrawerViewProps & { kind: string },
  ) => ReactElement;
  if (!kind) return null;
  return <View runId={runId} payload={payload} kind={kind} />;
}
