import { useMode } from "@/app/mode";

export function App() {
  const mode = useMode();
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8">
      <div className="flex items-center gap-2">
        <span
          className="h-2.5 w-2.5 rounded-full bg-algo"
          style={{ boxShadow: "0 0 8px var(--color-algo)" }}
        />
        <h1 className="text-lg font-semibold tracking-wide">operad</h1>
        <span className="text-muted">·</span>
        <span className="text-muted">{mode}</span>
      </div>
      <p className="max-w-md text-center text-sm text-muted">
        scaffold up. labeling + training launcher rebuilds in PR5.
      </p>
    </div>
  );
}
