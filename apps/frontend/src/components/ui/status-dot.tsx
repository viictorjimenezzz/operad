import { hashColor, hashColorGlow } from "@/lib/hash-color";
import { cn } from "@/lib/utils";

/**
 * Compact run-state dot. Three meanings:
 *  - `running`: pulsing green halo (W&B's live indicator)
 *  - `ended`:   solid neutral check
 *  - `error`:   solid red dot
 *
 * When `tone="identity"`, uses a hash-derived color from the palette.
 * That variant is what the tree uses for the colored dot beside each
 * group/run name (mirrors W&B's "this color = this group" everywhere).
 */
export type StatusDotState = "running" | "ended" | "error" | "idle";

export interface StatusDotProps {
  state?: StatusDotState;
  /** When set, the dot color comes from this identity hash. */
  identity?: string | null;
  size?: "xs" | "sm" | "md";
  pulse?: boolean;
  className?: string;
  title?: string;
}

const SIZE: Record<NonNullable<StatusDotProps["size"]>, number> = {
  xs: 6,
  sm: 8,
  md: 10,
};

export function StatusDot({
  state,
  identity,
  size = "sm",
  pulse,
  className,
  title,
}: StatusDotProps) {
  const px = SIZE[size];
  const useIdentity = identity != null;
  const color = useIdentity
    ? hashColor(identity)
    : state === "error"
      ? "var(--color-err)"
      : state === "running"
        ? "var(--color-ok)"
        : state === "ended"
          ? "var(--color-muted)"
          : "var(--color-muted-2)";
  const glow = useIdentity ? hashColorGlow(identity) : "var(--color-ok)";
  const showPulse = pulse ?? state === "running";

  return (
    <span
      title={title ?? state}
      className={cn("relative inline-flex flex-shrink-0", className)}
      style={{ width: px, height: px }}
    >
      {showPulse ? (
        <span
          aria-hidden
          className="absolute inset-0 animate-ping rounded-full"
          style={{ background: glow, opacity: 0.5 }}
        />
      ) : null}
      <span
        aria-hidden
        className="relative inline-block rounded-full"
        style={{
          width: px,
          height: px,
          background: color,
          boxShadow: useIdentity ? "0 0 0 1px rgba(255,255,255,0.06)" : undefined,
        }}
      />
    </span>
  );
}
