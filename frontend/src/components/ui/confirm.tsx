import { AlertTriangle } from "lucide-react";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  message: string;
  /** 确认按钮文案：必须动词描述动作（删除/清空/确认退出），禁止「确定/OK」（规范 7.10） */
  confirmLabel: string;
  cancelLabel?: string;
  /** 危险操作：左侧警示图标 + 确认按钮玫瑰色 */
  danger?: boolean;
  confirmLoading?: boolean;
  onConfirm: () => void;
}

/** 确认对话框（规范 7.10）：固定 max-w-md，三段结构，焦点默认在确认按钮 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger = false,
  confirmLoading = false,
  onConfirm,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      // 焦点落在确认按钮（规范 7.10：回车直接确认）
      window.setTimeout(() => confirmRef.current?.focus(), 50);
    }
  }, [open]);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-900/50 backdrop-blur-sm" />
        <DialogPrimitive.Content
          aria-label={title}
          className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-xl border border-surface-3 bg-surface-0 shadow-lg dark:border-ink-700 dark:bg-ink-700"
        >
          <div className="flex items-start gap-4 px-6 pt-5">
            {danger && (
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose-50 dark:bg-rose-900">
                <AlertTriangle className="h-5 w-5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
              </span>
            )}
            <DialogPrimitive.Title className="text-base font-semibold text-ink-900 dark:text-surface-0">{title}</DialogPrimitive.Title>
          </div>
          <div className="px-6 pb-4 pt-2">
            <p className="whitespace-pre-wrap text-sm leading-6 text-ink-700 dark:text-surface-4">{message}</p>
          </div>
          <div className="flex justify-end gap-2 border-t border-surface-3 bg-surface-1 px-6 py-4 dark:border-ink-900 dark:bg-ink-900">
            <Button
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={confirmLoading}
            >
              {cancelLabel ?? t("common.cancel")}
            </Button>
            <Button
              ref={confirmRef}
              variant={danger ? "danger" : "primary"}
              loading={confirmLoading}
              disabled={confirmLoading}
              onClick={onConfirm}
              className={cn(!danger && "bg-brand-600 text-white hover:bg-brand-700")}
            >
              {confirmLoading ? null : confirmLabel}
            </Button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
