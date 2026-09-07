import type { InputHTMLAttributes, ReactNode } from "react";
import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

/** 输入框统一基础样式（规范 7.4） */
export const inputBaseClass =
  "w-full rounded-lg border border-transparent bg-surface-2 px-3 py-2 text-sm text-ink-900 transition-colors duration-150 placeholder:text-ink-400 focus:border-brand-500 focus:bg-surface-0 focus:outline-none dark:border-transparent dark:bg-ink-900 dark:text-surface-0 dark:placeholder:text-surface-4 dark:focus:bg-ink-900 disabled:cursor-not-allowed disabled:opacity-50";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className, ...rest }: InputProps) {
  return <input className={cn(inputBaseClass, className)} {...rest} />;
}

export interface FieldProps {
  label?: ReactNode;
  required?: boolean;
  error?: string | null;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** 表单项包装：Label + 输入控件 + 错误/帮助文字（规范 7.4 表单通用规则） */
export function Field({ label, required, error, hint, children, className }: FieldProps) {
  const id = useId();
  return (
    <div className={cn("space-y-1.5", className)}>
      {label != null && (
        <label htmlFor={id} className="block text-sm font-medium text-ink-700 dark:text-surface-4">
          {label}
          {required && (
            <span className="ml-0.5 text-rose-500" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      <div className={cn(error && "[&>input]:border-rose-500 [&>input]:bg-surface-0")}>{children}</div>
      {error ? (
        <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-ink-400 dark:text-surface-4">{hint}</p>
      ) : null}
    </div>
  );
}

export interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {}

/** 密码输入：右侧眼睛切换可见性（规范 7.4.3） */
export function PasswordInput({ className, ...rest }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} className={cn("pr-10", className)} {...rest} />
      <button
        type="button"
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-400 hover:text-ink-900 dark:hover:text-surface-0"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "隐藏密码" : "显示密码"}
        tabIndex={-1}
      >
        {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
      </button>
    </div>
  );
}
