import { ErrorBoundary } from "@/app/ErrorBoundary";
import { type AppMode, ModeProvider } from "@/app/mode";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

interface ProvidersProps {
  mode: AppMode;
  children: ReactNode;
}

export function Providers({ mode, children }: ProvidersProps) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <ErrorBoundary>
      <ModeProvider mode={mode}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </ModeProvider>
    </ErrorBoundary>
  );
}
