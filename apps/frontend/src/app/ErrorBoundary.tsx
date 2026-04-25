import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("operad: uncaught error", error, info.componentStack);
  }

  override render(): ReactNode {
    const { error } = this.state;
    if (error === null) return this.props.children;

    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <h1 className="text-lg font-semibold text-err">operad ui crashed</h1>
        <pre className="max-w-3xl whitespace-pre-wrap rounded-md border border-border bg-bg-2 p-4 text-left font-mono text-xs text-muted">
          {error.stack ?? error.message}
        </pre>
        <button
          type="button"
          className="rounded-md border border-border bg-bg-2 px-3 py-1.5 text-xs hover:border-border-strong"
          onClick={() => this.setState({ error: null })}
        >
          dismiss
        </button>
      </div>
    );
  }
}
