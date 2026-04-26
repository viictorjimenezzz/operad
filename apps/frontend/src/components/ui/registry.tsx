import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Divider,
  EmptyState,
  Eyebrow,
  HashTag,
  KeyValueGrid,
  Pill,
  Section,
  Sparkline,
  StatTile,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui";
import type { ComponentRegistry } from "@json-render/react";

/** Strip undefined keys; resulting type drops `undefined` from value unions. */
function defined<T extends Record<string, unknown>>(
  obj: T,
): { [K in keyof T]?: Exclude<T[K], undefined> } {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) out[k] = v;
  }
  return out as { [K in keyof T]?: Exclude<T[K], undefined> };
}

/**
 * UI atoms registered as json-render components. The component is the
 * smallest unit a layout can address by name; higher-level "blocks"
 * compose these via further registry entries (see overview/registry).
 */
export const uiRegistry: ComponentRegistry = {
  Card: ({ element, children }) => {
    const props = element.props as {
      title?: string;
      flush?: boolean;
      variant?: "raised" | "flat" | "inset";
    };
    return (
      <Card {...defined({ variant: props.variant, flush: props.flush })}>
        {props.title ? (
          <CardHeader>
            <CardTitle>{props.title}</CardTitle>
          </CardHeader>
        ) : null}
        <CardContent>{children}</CardContent>
      </Card>
    );
  },
  Row: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 12;
    return (
      <div className="flex flex-wrap [&>*]:min-w-0 [&>*]:flex-1" style={{ gap }}>
        {children}
      </div>
    );
  },
  Col: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 12;
    return (
      <div className="flex flex-col" style={{ gap }}>
        {children}
      </div>
    );
  },
  Stack: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 8;
    return (
      <div className="flex flex-col" style={{ gap }}>
        {children}
      </div>
    );
  },
  Tabs: ({ element, children }) => {
    const tabs = (element.props as { tabs: Array<{ id: string; label: string }> }).tabs;
    const firstTab = tabs[0]?.id ?? "tab-0";
    const childArray = Array.isArray(children) ? children : [children];
    return (
      <Tabs defaultValue={firstTab} className="flex h-full flex-col">
        <TabsList>
          {tabs.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t, i) => (
          <TabsContent key={t.id} value={t.id} className="flex-1 overflow-auto">
            {childArray[i]}
          </TabsContent>
        ))}
      </Tabs>
    );
  },
  EmptyState: ({ element }) => {
    const props = element.props as { title?: string; description?: string };
    return (
      <EmptyState
        title={props.title ?? "No layout available"}
        {...defined({ description: props.description })}
      />
    );
  },
  Section: ({ element, children }) => {
    const p = element.props as {
      title: string;
      summary?: string;
      defaultOpen?: boolean;
      disabled?: boolean;
    };
    return (
      <Section
        title={p.title}
        {...defined({ summary: p.summary, defaultOpen: p.defaultOpen, disabled: p.disabled })}
      >
        {children}
      </Section>
    );
  },
  Eyebrow: ({ element }) => {
    const p = element.props as { text: string; tone?: "default" | "muted" | "accent" };
    return <Eyebrow {...defined({ tone: p.tone })}>{p.text}</Eyebrow>;
  },
  StatTile: ({ element }) => {
    const p = element.props as {
      label: string;
      value: string | number;
      sub?: string;
      size?: "sm" | "md" | "lg";
      align?: "left" | "right";
    };
    return (
      <StatTile
        label={p.label}
        value={p.value ?? "—"}
        {...defined({ sub: p.sub, size: p.size, align: p.align })}
      />
    );
  },
  HashTag: ({ element }) => {
    const p = element.props as {
      hash?: string | null;
      label?: string;
      sub?: string;
      size?: "sm" | "md" | "lg";
    };
    return <HashTag hash={p.hash} {...defined({ label: p.label, sub: p.sub, size: p.size })} />;
  },
  Pill: ({ element, children }) => {
    const p = element.props as {
      tone?: "default" | "live" | "ok" | "warn" | "error" | "accent" | "algo";
      pulse?: boolean;
      text?: string;
    };
    return <Pill {...defined({ tone: p.tone, pulse: p.pulse })}>{p.text ?? children}</Pill>;
  },
  Sparkline: ({ element }) => {
    const p = element.props as {
      values: Array<number | null>;
      width?: number;
      height?: number;
    };
    return <Sparkline values={p.values ?? []} {...defined({ width: p.width, height: p.height })} />;
  },
  KeyValueGrid: ({ element }) => {
    const p = element.props as {
      rows: Array<{ key: string; value: string; mono?: boolean }>;
      density?: "default" | "compact";
    };
    return <KeyValueGrid rows={p.rows ?? []} {...defined({ density: p.density })} />;
  },
  Divider: () => <Divider />,
};
