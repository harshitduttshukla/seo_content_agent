import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "secondary" | "danger";
};

export function Button({ className = "", tone = "primary", ...props }: ButtonProps) {
  const tones = {
    primary: "bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]",
    secondary:
      "border border-[var(--border)] bg-white text-[var(--ink)] hover:bg-[var(--surface-soft)]",
    danger: "bg-[var(--danger)] text-white hover:opacity-90",
  };
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-[10px] px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${tones[tone]} ${className}`}
      {...props}
    />
  );
}
