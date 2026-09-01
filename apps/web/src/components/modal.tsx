"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

export function Modal({
  open = true,
  title,
  children,
  onClose,
}: {
  open?: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !ref.current?.open) ref.current?.showModal();
    if (!open && ref.current?.open) ref.current?.close();
  }, [open]);
  return (
    <dialog
      className="w-[min(92vw,34rem)] rounded-[var(--radius)] border border-[var(--border)] bg-white p-0 shadow-[var(--shadow)] backdrop:bg-[#111827aa]"
      onCancel={onClose}
      onClose={onClose}
      ref={ref}
    >
      <header className="flex items-center justify-between border-b border-[var(--border)] p-5">
        <h2 className="m-0 text-lg font-bold">{title}</h2>
        <button aria-label="Close dialog" className="rounded-lg p-2 hover:bg-[var(--surface-soft)]" onClick={onClose}>
          <X aria-hidden size={18} />
        </button>
      </header>
      <div className="p-5">{children}</div>
    </dialog>
  );
}
