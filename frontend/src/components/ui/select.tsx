import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface SelectOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
}

export interface SelectProps<T extends string> {
  value: T;
  options: Array<SelectOption<T>>;
  onChange: (value: T) => void;
  /** 无障碍标签 */
  label?: string;
  disabled?: boolean;
  className?: string;
}

/** 下拉选择（规范 7.4.6）：文本+箭头结构、覆盖更新、点外/Esc 关闭 */
export function Select<T extends string>({ value, options, onChange, label, disabled, className }: SelectProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const id = useId();
  const current = options.find((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        id={id}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded-lg border border-transparent bg-surface-2 px-3 py-2 text-sm text-ink-900 transition-colors duration-150 hover:border-surface-3 focus:border-brand-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 dark:bg-ink-900 dark:text-surface-0",
        )}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={cn("truncate", !current && "text-ink-400")}>{current ? current.label : "…"}</span>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-ink-400 transition-transform duration-200", open && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {open && (
        <div
          role="listbox"
          aria-labelledby={id}
          className="absolute left-0 top-full z-50 mt-1 max-h-60 w-full min-w-[200px] overflow-y-auto rounded-lg border border-surface-3 bg-surface-0 py-1 shadow-md scrollbar-thin dark:border-ink-700 dark:bg-ink-700"
        >
          {options.map((o) => {
            const selected = o.value === value;
            return (
              <button
                key={o.value}
                type="button"
                role="option"
                aria-selected={selected}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors duration-150",
                  selected
                    ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-900 dark:text-brand-300"
                    : "text-ink-700 hover:bg-surface-2 dark:text-surface-4 dark:hover:bg-ink-900",
                )}
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                }}
              >
                <span className="truncate">{o.label}</span>
                {o.hint && <span className="ml-auto truncate text-xs text-ink-400">{o.hint}</span>}
                {selected && <Check className="h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden="true" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
