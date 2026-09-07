import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors duration-150 select-none whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]",
  {
    variants: {
      variant: {
        primary: "bg-brand-600 text-white hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
        secondary:
          "bg-surface-0 border border-surface-3 text-ink-700 hover:bg-surface-2 dark:border-ink-700 dark:bg-ink-700 dark:text-surface-0 dark:hover:bg-ink-900",
        ghost: "text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300",
        danger: "bg-rose-600 text-white hover:bg-rose-700",
      },
      size: {
        default: "px-4 py-2",
        sm: "px-3 py-1.5 text-xs",
        icon: "w-9 h-9",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** loading 时显示旋转图标并隐藏文字，按钮禁用（规范 7.1） */
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, loading, icon, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-disabled={disabled || loading || undefined}
      {...rest}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </button>
  );
});
