/**
 * Zod schema for our internal LayoutSpec — the JSON shape every
 * per-algorithm layout file under src/layouts/ must conform to. The
 * spec block itself maps 1:1 to @json-render/core's UITree once each
 * element gets `key` injected from its map id (done in
 * <DashboardRenderer />, PR3).
 */
import { z } from "zod";

export const GenericElementSpec = z.object({
  type: z.string(),
  props: z.record(z.unknown()).optional(),
  children: z.array(z.string()).optional(),
});
export type GenericElementSpec = z.infer<typeof GenericElementSpec>;

export const TabsElementSpec = z.object({
  type: z.literal("Tabs"),
  props: z.object({
    tabs: z.array(
      z.object({
        id: z.string(),
        label: z.string(),
        badge: z.union([z.string(), z.number()]).optional(),
        condition: z.string().optional(),
      }),
    ),
  }),
  children: z.array(z.string()),
});
export type TabsElementSpec = z.infer<typeof TabsElementSpec>;

export const ElementSpec = z.union([TabsElementSpec, GenericElementSpec]);
export type ElementSpec = z.infer<typeof ElementSpec>;

export const DataSourceSpec = z.object({
  endpoint: z.string(),
  queryKey: z.array(z.unknown()).optional(),
  stream: z.string().optional(),
  mergeMode: z.enum(["replace", "append", "map"]).optional(),
});
export type DataSourceSpec = z.infer<typeof DataSourceSpec>;

export const LayoutSpec = z.object({
  algorithm: z.string(),
  version: z.literal(1),
  dataSources: z.record(DataSourceSpec).default({}),
  spec: z.object({
    root: z.string(),
    elements: z.record(ElementSpec),
  }),
});
export type LayoutSpec = z.infer<typeof LayoutSpec>;

/**
 * Resolve a layout's data-source endpoint / stream URL by substituting
 * `$context.runId`, `$context.algorithmPath`, etc. We keep this tiny
 * (no Handlebars / Liquid).
 */
export function resolvePath(template: string, context: Record<string, string>): string {
  return template.replace(/\$context\.([a-zA-Z0-9_]+)/g, (_, key: string) => {
    const value = context[key];
    if (value === undefined) {
      throw new Error(`layout: $context.${key} is not in resolution context`);
    }
    return value;
  });
}
