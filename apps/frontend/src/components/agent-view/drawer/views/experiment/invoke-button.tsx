import { Button } from "@/components/ui/button";

interface InvokeButtonProps {
  running: boolean;
  onRun: () => void;
  disabled?: boolean;
}

export function InvokeButton({ running, onRun, disabled }: InvokeButtonProps) {
  return (
    <Button size="sm" variant="primary" disabled={running || disabled} onClick={onRun}>
      {running ? "running..." : "run"}
    </Button>
  );
}
