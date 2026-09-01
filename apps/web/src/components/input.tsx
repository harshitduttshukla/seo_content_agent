import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

export function Input({ label, hint, className = "", id, ...props }: InputProps) {
  const inputId = id ?? props.name;
  return (
    <label className="grid gap-2 text-sm font-semibold text-[var(--ink)]" htmlFor={inputId}>
      {label}
      <input
        id={inputId}
        className={`min-h-11 w-full rounded-[10px] border border-[var(--border)] bg-white px-3 text-sm font-normal shadow-sm transition placeholder:text-[#9aa3b3] focus:border-[var(--accent)] ${className}`}
        {...props}
      />
      {hint ? <span className="text-xs font-normal text-[var(--muted)]">{hint}</span> : null}
    </label>
  );
}
