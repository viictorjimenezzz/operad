import { getDrawerView } from "@/components/agent-view/drawer/drawer-registry";
import { DrawerStub } from "@/components/agent-view/drawer/views/_stub";
import { useUIStore } from "@/stores";
import type { DrawerKind, DrawerPayload } from "@/stores/ui";
import { useParams } from "react-router-dom";

const TITLE_BY_KIND: Record<Exclude<DrawerKind, null>, string> = {
  langfuse: "Langfuse trace",
  events: "Filtered events",
  prompts: "Prompt diff",
  values: "Value timeline",
  "find-runs": "Find runs",
  experiment: "Prompt experiment",
};

function subtitleFromPayload(payload: DrawerPayload): string | null {
  return typeof payload.agentPath === "string" ? payload.agentPath : null;
}

export function getDrawerHeader(
  drawer: {
    kind: Exclude<DrawerKind, null>;
    payload: DrawerPayload;
  },
  runId: string,
): { title: string; subtitle: string | null } {
  const view = getDrawerView(drawer.kind);
  if (!view) {
    return {
      title: TITLE_BY_KIND[drawer.kind],
      subtitle: subtitleFromPayload(drawer.payload),
    };
  }
  return {
    title: view.getTitle(drawer.payload, runId),
    subtitle: view.getSubtitle?.(drawer.payload, runId) ?? subtitleFromPayload(drawer.payload),
  };
}

export function DrawerHost() {
  const drawer = useUIStore((s) => s.drawer);
  const { runId = "" } = useParams<{ runId: string }>();

  if (!drawer) return null;

  const view = getDrawerView(drawer.kind);
  if (!view) return <DrawerStub kind={drawer.kind} payload={drawer.payload} runId={runId} />;

  return view.render({ payload: drawer.payload, runId });
}
