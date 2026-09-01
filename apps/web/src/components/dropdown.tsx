import type { SelectHTMLAttributes } from "react";

export function Dropdown({
  label,
  children,
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <label className="grid gap-2 text-sm font-semibold">
      {label}
      <select
        className={`min-h-11 rounded-[10px] border border-[var(--border)] bg-white px-3 font-normal ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
