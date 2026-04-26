import { EmptyState } from "@/components/ui/empty-state";

export function RunListPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <EmptyState
        title="select a run"
        description="choose a run from the sidebar to view its details"
      />
    </div>
  );
}
