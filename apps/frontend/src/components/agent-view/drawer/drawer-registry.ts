import type { DrawerKind, DrawerPayload } from "@/stores";
import type { ComponentType } from "react";

export interface DrawerViewProps {
  runId: string;
  payload: DrawerPayload;
}

export interface DrawerViewRegistration {
  component: ComponentType<DrawerViewProps>;
  getTitle?: (payload: DrawerPayload) => string;
}

const registry = new Map<Exclude<DrawerKind, null>, DrawerViewRegistration>();

export function registerDrawerView(
  kind: Exclude<DrawerKind, null>,
  view: DrawerViewRegistration,
): void {
  registry.set(kind, view);
}

export function getDrawerView(kind: DrawerKind): DrawerViewRegistration | null {
  if (kind == null) return null;
  return registry.get(kind) ?? null;
}

export function ensureDefaultDrawerViews(): void {
  if (registry.size > 0) return;
}
