"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@iconify/react";

const items = [
  { href: "/", label: "Overview", icon: "lucide:layout-dashboard" },
  { href: "/leads", label: "Leads", icon: "lucide:inbox" },
  { href: "/sources", label: "Sources", icon: "lucide:radio-tower" },
  { href: "/profile", label: "Profile", icon: "lucide:user" },
  { href: "/settings", label: "Settings", icon: "lucide:settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-surface px-3 py-5 flex flex-col gap-1">
      <div className="px-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" />
          <span className="font-semibold tracking-tight">leads-bot</span>
        </div>
        <div className="uppercase-label mt-1">control</div>
      </div>
      {items.map((it) => {
        const active = path === it.href || (it.href !== "/" && path.startsWith(it.href));
        return (
          <Link
            key={it.href}
            href={it.href}
            className={[
              "flex items-center gap-2.5 px-3 h-9 rounded-md text-sm transition-colors",
              active
                ? "bg-surfaceHi text-text"
                : "text-textMuted hover:text-text hover:bg-surface",
            ].join(" ")}
          >
            <Icon icon={it.icon} width={16} />
            {it.label}
          </Link>
        );
      })}
    </aside>
  );
}
