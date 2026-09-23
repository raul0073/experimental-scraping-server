"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** "Next round" lives at "/" now that the predictor is the front page, but
 *  /predictor still resolves, so the tab matches either address rather than
 *  the one it links to — otherwise arriving on the old URL lights up nothing
 *  and the row claims you are somewhere you are not. */
const TABS = [
  { href: "/", label: "Next round", at: ["/", "/predictor"] },
  { href: "/predictor/projected", label: "Projected tables", at: ["/predictor/projected"] },
  { href: "/predictor/history", label: "Track record", at: ["/predictor/history"] },
];

export function SubNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1.5">
      {TABS.map((t) => {
        const active = t.at.includes(pathname ?? "");
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
