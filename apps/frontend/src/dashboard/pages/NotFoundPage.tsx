import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <EmptyState
        title="not found"
        description="this route doesn't exist in the operad dashboard."
        cta={
          <Link to="/">
            <Button variant="primary" size="sm">
              back to runs
            </Button>
          </Link>
        }
      />
    </div>
  );
}
