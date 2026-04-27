import { cn } from "@/lib/utils";
import { MoreHorizontal } from "lucide-react";
import {
  type HTMLAttributes,
  type ReactNode,
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

/**
 * A flat W&B-style ChartCard. The single building block of the
 * workspace canvas: title-left, legend/actions-right, generous content
 * area below, optional kebab menu.
 *
 * Replaces the click-to-expand `Section` for canvas content. Keep
 * `Section` for forms / lists / settings; use `PanelCard` for
 * everything that belongs in a workspace grid.
 */
export interface PanelCardProps extends HTMLAttributes<HTMLDivElement> {
  title?: ReactNode;
  /** Small label rendered before the title (W&B "System" eyebrow). */
  eyebrow?: ReactNode;
  /** Right-aligned legend / pills / pager. */
  toolbar?: ReactNode;
  /** Drop the inner padding (children own their layout). */
  flush?: boolean;
  /** Force a min content height; useful for chart panels. */
  bodyMinHeight?: number;
  /** Visual weight: `panel` (default) is the flat workspace tile; `inset` is darker. */
  surface?: "panel" | "inset";
  /** Hide top border + title; useful when nesting in a parent panel. */
  bare?: boolean;
  /** Optional kebab-menu items. */
  menu?: PanelMenuItem[];
}

export interface PanelMenuItem {
  id: string;
  label: string;
  onSelect: () => void;
  danger?: boolean;
  disabled?: boolean;
}

const SURFACE: Record<NonNullable<PanelCardProps["surface"]>, string> = {
  panel: "border border-border bg-bg-1",
  inset: "border border-border bg-bg-inset",
};

export const PanelCard = forwardRef<HTMLDivElement, PanelCardProps>(
  (
    {
      title,
      eyebrow,
      toolbar,
      flush,
      bodyMinHeight,
      surface = "panel",
      bare,
      menu,
      className,
      children,
      ...rest
    },
    ref,
  ) => {
    const showHeader = !bare && (title != null || eyebrow != null || toolbar != null || menu);

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-lg shadow-[var(--shadow-card-soft)] transition-colors",
          SURFACE[surface],
          "hover:border-border-strong",
          className,
        )}
        {...rest}
      >
        {showHeader ? (
          <div className="flex items-start gap-3 border-b border-border px-3 py-2">
            <div className="min-w-0 flex-1">
              {eyebrow != null ? (
                <div className="mb-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-2">
                  {eyebrow}
                </div>
              ) : null}
              {title != null ? (
                <div className="truncate text-[13px] font-medium text-text">{title}</div>
              ) : null}
            </div>
            {toolbar != null ? (
              <div className="flex shrink-0 items-center gap-2">{toolbar}</div>
            ) : null}
            {menu && menu.length > 0 ? <PanelMenu items={menu} /> : null}
          </div>
        ) : null}
        <div
          className={cn(flush ? "" : "p-3")}
          style={bodyMinHeight ? { minHeight: bodyMinHeight } : undefined}
        >
          {children}
        </div>
      </div>
    );
  },
);
PanelCard.displayName = "PanelCard";

function PanelMenu({ items }: { items: PanelMenuItem[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current) return;
      if (e.target instanceof Node && ref.current.contains(e.target)) return;
      close();
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open, close]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="panel menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded p-1 text-muted-2 transition-colors hover:bg-bg-3 hover:text-text"
      >
        <MoreHorizontal size={14} />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-30 mt-1 w-40 overflow-hidden rounded-md border border-border-strong bg-bg-1 shadow-[var(--shadow-popover)]"
        >
          {items.map((it) => (
            <button
              key={it.id}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              onClick={() => {
                if (!it.disabled) {
                  it.onSelect();
                  close();
                }
              }}
              className={cn(
                "block w-full px-3 py-1.5 text-left text-[12px] transition-colors",
                it.disabled
                  ? "cursor-not-allowed text-muted-2"
                  : it.danger
                    ? "text-[--color-err] hover:bg-bg-2"
                    : "text-text hover:bg-bg-2",
              )}
            >
              {it.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
