"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/predictor", label: "Next round" },
  { href: "/predictor/projected", label: "Projected tables" },
  { href: "/predictor/history", label: "Track record" },
];

export function SubNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1.5">
      {TABS.map((t) => {
        const active = pathname === t.href;
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium transition-colors ${
              active
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
