import { Outlet } from "react-router-dom";

export function StudioShell() {
  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 items-center gap-3 border-b border-border bg-bg-1 px-4 text-xs">
        <span
          className="h-2.5 w-2.5 rounded-full bg-algo"
          style={{ boxShadow: "0 0 8px var(--color-algo)" }}
        />
        <span className="font-semibold tracking-wide">operad</span>
        <span className="text-muted">studio</span>
      </header>
      <main aria-label="studio" className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
