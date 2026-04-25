import { type ReactNode, createContext, useContext } from "react";

export type AppMode = "dashboard" | "studio";

const ModeContext = createContext<AppMode | null>(null);

export function ModeProvider({ mode, children }: { mode: AppMode; children: ReactNode }) {
  return <ModeContext.Provider value={mode}>{children}</ModeContext.Provider>;
}

export function useMode(): AppMode {
  const value = useContext(ModeContext);
  if (value === null) throw new Error("useMode() must be used inside <ModeProvider>");
  return value;
}
