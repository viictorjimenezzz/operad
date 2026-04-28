import { IconButton } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

export interface ParameterDrawerProps {
  open: boolean;
  identity: string;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}

export function ParameterDrawer({
  open,
  identity,
  title,
  subtitle,
  onClose,
  children,
}: ParameterDrawerProps) {
  const [mounted, setMounted] = useState(open);

  useEffect(() => {
    if (open) setMounted(true);
  }, [open]);

  useEffect(() => {
    if (!mounted) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [mounted, onClose]);

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50" aria-hidden={!open}>
      <button
        type="button"
        aria-label="close parameter drawer"
        className={cn(
          "absolute inset-0 cursor-default bg-black/45 transition-opacity duration-[var(--motion-inspector)] ease-[var(--motion-ease-out)]",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <dialog
        open={mounted}
        aria-modal="true"
        aria-labelledby="parameter-drawer-title"
        className={cn(
          "m-0 h-full border-0 p-0",
          "absolute inset-y-0 left-auto right-0 flex w-[clamp(var(--drawer-min),var(--drawer-width),var(--drawer-max))] max-w-full bg-bg-1 text-text shadow-[var(--shadow-inspector)] transition-transform duration-[var(--motion-inspector)] ease-[var(--motion-ease-out)]",
          open ? "translate-x-0" : "translate-x-full",
        )}
        onTransitionEnd={() => {
          if (!open) setMounted(false);
        }}
      >
        <div className="w-[4px] flex-shrink-0" style={{ background: hashColor(identity) }} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-start gap-3 border-b border-border px-5 py-4">
            <div className="min-w-0 flex-1">
              <div
                id="parameter-drawer-title"
                className="truncate text-[18px] font-medium leading-tight text-text"
              >
                {title}
              </div>
              {subtitle ? (
                <div className="mt-1 truncate font-mono text-[11px] text-muted-2">{subtitle}</div>
              ) : null}
            </div>
            <IconButton aria-label="close parameter drawer" onClick={onClose}>
              <X size={14} />
            </IconButton>
          </header>
          <div className="min-h-0 flex-1 overflow-auto">{children}</div>
        </div>
      </dialog>
    </div>,
    document.body,
  );
}
