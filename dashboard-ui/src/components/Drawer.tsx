"use client";
import { useEffect } from "react";
import { Icon } from "@iconify/react";

type Props = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: number;
};

export function Drawer({ open, onClose, title, children, width = 560 }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className={[
          "fixed inset-0 bg-black/60 transition-opacity z-40",
          open ? "opacity-100" : "opacity-0 pointer-events-none",
        ].join(" ")}
        aria-hidden
      />
      <aside
        className={[
          "fixed inset-y-0 right-0 z-50 bg-surface border-l border-border",
          "transition-transform duration-200 flex flex-col",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
        style={{ width }}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between px-5 h-14 border-b border-border shrink-0">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-sm p-1 hover:bg-surfaceHi"
          >
            <Icon icon="lucide:x" width={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </>
  );
}
