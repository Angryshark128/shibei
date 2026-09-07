import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  /** 宽：md=448 / lg=512 / xl=672（规范 7.7） */
  size?: "md" | "lg" | "xl";
  children: ReactNode;
  footer?: ReactNode;
}

/** 弹窗（规范 7.7）：遮罩 blur、焦点圈闭、Esc/遮罩/关闭按钮可关 */
export function Modal({ open, onOpenChange, title, size = "md", children, footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const width = size === "md" ? "max-w-md" : size === "lg" ? "max-w-lg" : "max-w-2xl";

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-900/50 backdrop-blur-sm" />
        <DialogPrimitive.Content
          aria-label={typeof title === "string" ? title : undefined}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-surface-3 bg-surface-0 shadow-lg dark:border-ink-700 dark:bg-ink-700",
            width,
          )}
        >
          <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-3">
            <DialogPrimitive.Title className="text-base font-semibold text-ink-900 dark:text-surface-0">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label="关闭"
              className="rounded-lg p-1 text-ink-400 transition-colors duration-150 hover:bg-surface-2 hover:text-ink-900 dark:hover:bg-ink-900 dark:hover:text-surface-0"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
          <div className="max-h-[65vh] overflow-y-auto px-6 pb-4 scrollbar-thin">{children}</div>
          {footer && <div className="flex justify-end gap-2 border-t border-surface-3 bg-surface-1 px-6 py-4 dark:border-ink-900 dark:bg-ink-900">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
