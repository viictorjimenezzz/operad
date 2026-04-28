import { hashColor } from "@/lib/hash-color";
import { useUIStore } from "@/stores";
import { GitBranch, X } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * Floating "compare basket" — shows runs the user has tagged for
 * cross-page comparison. Opens `/experiments?runs=...` on click.
 *
 * The basket persists across navigation (zustand+localStorage), so the
 * user can pick a run from the Algorithms rail, navigate to Agents,
 * pick another, then hit Compare.
 */
export function CompareBasket() {
  const basket = useUIStore((s) => s.compareBasket);
  const remove = useUIStore((s) => s.removeFromCompare);
  const clear = useUIStore((s) => s.clearCompare);
  if (basket.length === 0) return null;

  const href = `/experiments?runs=${basket.map(encodeURIComponent).join(",")}`;
  return (
    <div
      role="region"
      aria-label="compare basket"
      className="pointer-events-auto fixed bottom-3 right-3 z-40 flex max-w-[480px] items-center gap-2 rounded-md border border-border-strong bg-bg-1 px-2 py-1.5 shadow-[var(--shadow-popover)]"
    >
      <GitBranch size={13} className="text-accent" />
      <span className="text-[11px] font-medium uppercase tracking-[0.06em] text-muted-2">
        compare
      </span>
      <span className="font-mono text-[11px] tabular-nums text-text">{basket.length}</span>
      <ul className="flex max-w-[260px] items-center gap-1 overflow-x-auto">
        {basket.slice(0, 6).map((id) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => remove(id)}
              className="inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-muted transition-colors hover:border-border-strong hover:text-text"
              title={`remove ${id}`}
            >
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: hashColor(id) }}
              />
              <span className="truncate">{shortId(id)}</span>
              <X size={10} aria-hidden />
            </button>
          </li>
        ))}
        {basket.length > 6 ? (
          <li className="font-mono text-[10px] text-muted-2">+{basket.length - 6}</li>
        ) : null}
      </ul>
      <span className="mx-1 h-4 w-px bg-border" />
      {basket.length >= 2 ? (
        <Link
          to={href}
          className="rounded bg-accent px-2 py-0.5 text-[11px] font-medium text-bg transition-colors hover:bg-[--color-accent-strong]"
        >
          Compare
        </Link>
      ) : (
        <span className="text-[11px] text-muted-2">add a 2nd run to compare</span>
      )}
      <button
        type="button"
        onClick={clear}
        className="text-[11px] text-muted transition-colors hover:text-text"
        aria-label="clear compare basket"
      >
        clear
      </button>
    </div>
  );
}

function shortId(id: string): string {
  return id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-3)}` : id;
}
