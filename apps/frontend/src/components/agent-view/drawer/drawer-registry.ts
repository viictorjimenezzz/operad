import type { DrawerKind, DrawerPayload } from "@/stores/ui";
import type { JSX } from "react";

export type DrawerViewKind = Exclude<DrawerKind, null>;

export interface DrawerRenderProps {
  payload: DrawerPayload;
  runId: string;
}

export interface DrawerViewRegistration {
  render: (props: DrawerRenderProps) => JSX.Element;
  getTitle: (payload: DrawerPayload, runId: string) => string;
  getSubtitle?: (payload: DrawerPayload, runId: string) => string | null;
}

const registry = new Map<DrawerViewKind, DrawerViewRegistration>();

export function registerDrawerView(kind: DrawerViewKind, view: DrawerViewRegistration): void {
  registry.set(kind, view);
}

export function getDrawerView(kind: DrawerViewKind): DrawerViewRegistration | null {
  return registry.get(kind) ?? null;
}
