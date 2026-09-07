import * as RadixSwitch from "@radix-ui/react-switch";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  /** 开关左侧标签 */
  label?: ReactNode;
  /** 无障碍名称（无 label 时必填） */
  "aria-label"?: string;
}

/** 开关（规范 7.4.8）：轨道 11x6，开=品牌色，关=surface-4 */
export function Switch({ checked, onCheckedChange, disabled, label, ...rest }: SwitchProps) {
  const control = (
    <RadixSwitch.Root
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-brand-600 dark:bg-brand-500" : "bg-surface-4 dark:bg-ink-900",
      )}
      {...rest}
    >
      <RadixSwitch.Thumb
        className={cn(
          "block h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-200 will-change-transform",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </RadixSwitch.Root>
  );

  if (!label) return control;
  return (
    <label className="flex cursor-pointer items-center gap-3">
      <span className="text-sm text-ink-700 dark:text-surface-4">{label}</span>
      {control}
    </label>
  );
}
