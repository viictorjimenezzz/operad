import { cn } from "@/lib/utils";
import { type VariantProps, cva } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-lg border text-[12px] font-medium transition-[background,border-color,color,box-shadow] duration-[var(--motion-quick)] ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent-dim] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "border-border bg-bg-2 text-text hover:border-border-strong hover:bg-bg-3",
        primary:
          "border-[--color-accent-dim] bg-[--color-accent-dim] text-[--color-accent-strong] hover:border-accent hover:bg-accent hover:text-bg",
        ghost: "border-transparent bg-transparent text-muted hover:text-text hover:bg-bg-3",
        outline: "border-border-strong bg-transparent text-text hover:bg-bg-3",
        danger:
          "border-[--color-err-dim] bg-[--color-err-dim] text-[--color-err] hover:bg-[--color-err] hover:text-bg",
      },
      size: {
        sm: "h-7 px-2.5",
        md: "h-8 px-3.5",
        lg: "h-10 px-5 text-[13px]",
        icon: "h-8 w-8 p-0",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...rest}
    />
  ),
);
Button.displayName = "Button";

export { buttonVariants };
