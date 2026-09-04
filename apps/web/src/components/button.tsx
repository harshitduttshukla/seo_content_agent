import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "secondary" | "danger";
  variant?: "primary" | "secondary" | "danger" | "outline" | "ghost" | string;
  size?: "sm" | "md" | "lg" | string;
};

export function Button({ className = "", tone = "primary", variant, size, ...props }: ButtonProps) {
  const effectiveTone = (variant === "secondary" || variant === "outline" || variant === "ghost") ? "secondary" : (variant === "danger" ? "danger" : tone);
  const tones = {
    primary: "bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]",
    secondary:
      "border border-[var(--border)] bg-white text-[var(--ink)] hover:bg-[var(--surface-soft)]",
    danger: "bg-[var(--danger)] text-white hover:opacity-90",
  };
  const sizeClasses = size === "sm" ? "min-h-8 px-2.5 py-1 text-xs" : size === "lg" ? "min-h-12 px-5 py-3 text-base" : "min-h-10 px-4 py-2 text-sm";
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-[10px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${tones[effectiveTone]} ${sizeClasses} ${className}`}
      {...props}
    />
  );
}
