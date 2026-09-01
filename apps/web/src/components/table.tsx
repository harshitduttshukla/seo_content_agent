import type { HTMLAttributes, TableHTMLAttributes } from "react";

export function Table(props: TableHTMLAttributes<HTMLTableElement>) {
  return <table className="w-full border-collapse text-left text-sm" {...props} />;
}

export function TableCell({ className = "", ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <td className={`border-b border-[var(--border)] px-4 py-3 ${className}`} {...props} />;
}

export function TableHead({ className = "", ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return <th className={`border-b border-[var(--border)] px-4 py-3 text-xs uppercase tracking-wider text-[var(--muted)] ${className}`} {...props} />;
}
