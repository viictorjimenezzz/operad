import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui";
import type { ComponentRegistry } from "@json-render/react";

export const uiRegistry: ComponentRegistry = {
  Card: ({ element, children }) => {
    const title = (element.props as { title?: string }).title;
    return (
      <Card>
        {title ? (
          <CardHeader>
            <CardTitle>{title}</CardTitle>
          </CardHeader>
        ) : null}
        <CardContent>{children}</CardContent>
      </Card>
    );
  },
  Row: ({ element, children }) => {
    const gap = (element.props as { gap?: number }).gap ?? 12;
    return (
      <div className="flex flex-wrap gap-3 [&>*]:min-w-0 [&>*]:flex-1" style={{ gap }}>
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
      <EmptyState title={props.title ?? "No layout available"} description={props.description} />
    );
  },
};
