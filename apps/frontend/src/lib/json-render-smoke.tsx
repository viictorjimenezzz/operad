/**
 * Smoke verifying that @json-render/{core,react} expose the API the
 * future <DashboardRenderer /> (PR3) is built around: createCatalog
 * for the schema, plain ComponentRegistry for the implementations,
 * <Renderer tree={UITree} registry={...} /> for the render call.
 *
 * If upstream API drifts, this fails fast at typecheck time and we
 * adapt the wrapper rather than every layout JSON.
 */
import { type UITree, createCatalog } from "@json-render/core";
import { type ComponentRegistry, Renderer } from "@json-render/react";
import { z } from "zod";

const cardProps = z.object({ title: z.string() });

export const smokeCatalog = createCatalog({
  name: "smoke",
  components: {
    Card: { props: cardProps, hasChildren: true, description: "container" },
  },
});

const Card: ComponentRegistry["Card"] = ({ element, children }) => {
  const { title } = cardProps.parse(element.props);
  return (
    <section className="rounded-md border border-border bg-bg-2 p-3">
      <header className="text-xs uppercase tracking-wider text-muted">{title}</header>
      <div>{children}</div>
    </section>
  );
};

export const smokeRegistry: ComponentRegistry = { Card };

export const smokeTree: UITree = {
  root: "outer",
  elements: {
    outer: { key: "outer", type: "Card", props: { title: "outer" }, children: ["inner"] },
    inner: { key: "inner", type: "Card", props: { title: "inner" } },
  },
};

export function SmokeRenderer() {
  return <Renderer tree={smokeTree} registry={smokeRegistry} />;
}
