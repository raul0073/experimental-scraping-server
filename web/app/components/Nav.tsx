"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** The header, cut down to what a reader comes for.
 *
 *  TWO THINGS, AND A DRAWER. The site does two jobs — it predicts fixtures
 *  and it rates the sides and players behind them — and everything else is
 *  something you read once: how it works, what was tried and rejected, the
 *  component lab. Those were sitting in the top row competing with the
 *  products, which made a four-item nav look like four equal offers.
 *
 *  FIXTURE CAME OUT ALTOGETHER. It is not a destination any more: you reach
 *  a match by clicking one in the predictor, which is the only way anyone
 *  would want to. A nav item for it invited people to arrive with no
 *  fixture chosen, which is the emptiest version of the page.
 *
 *  Matched on the first path segment rather than on equality, so a team page
 *  at /team/arsenal still lights up Ratings — it is reached from that table
 *  and belongs to it, even though it lives at its own route.
 */
/** PREDICTOR POINTS AT "/" NOW, because the predictor IS the front page.
 *  It still owns the /predictor route, which survives as an alias, so a
 *  bookmark to the old address lights up the right tab. */
const MAIN = [
  { href: "/", label: "Predictor", owns: ["", "predictor", "versus"] },
  { href: "/ratings", label: "Ratings", owns: ["ratings", "team", "teams"] },
  // A third product rather than a drawer item: the drawer is for things you
  // read once, and a ranking is not one of them.
];

const MORE = [
  { href: "/how-it-works", label: "How it works", owns: ["how-it-works"] },
  { href: "/rejected", label: "What we rejected", owns: ["rejected"] },
];

export function Nav() {
  const path = usePathname() ?? "/";
  const head = path.split("/")[1] ?? "";
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  /** A drawer that does not close when you look away is a drawer that
   *  covers the page you were trying to read. */
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const link = (here: boolean) =>
    here
      ? "border-b-2 border-home pb-0.5 font-medium text-ink"
      : "border-b-2 border-transparent pb-0.5 text-ink-2 transition-colors hover:text-ink";

  const inMore = MORE.some((m) => m.owns.includes(head));

  return (
    <nav className="flex items-center gap-5 text-[13.5px]">
      {MAIN.map((n) => (
        <Link
          key={n.href}
          href={n.href}
          aria-current={n.owns.includes(head) ? "page" : undefined}
          className={link(n.owns.includes(head))}
        >
          {n.label}
        </Link>
      ))}

      <div className="relative" ref={box}>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={link(inMore) + " cursor-pointer"}
        >
          More
          <span className="ml-1 text-[10px] text-ink-3">{open ? "▴" : "▾"}</span>
        </button>
        {open && (
          <div className="absolute right-0 z-30 mt-2 w-48 overflow-hidden rounded-lg border border-line bg-card shadow-lg">
            {MORE.map((m) => (
              <Link
                key={m.href}
                href={m.href}
                onClick={() => setOpen(false)}
                className={`block px-3 py-2 text-[13px] transition-colors hover:bg-[#f4f6f8] ${
                  m.owns.includes(head) ? "font-medium text-ink" : "text-ink-2"
                }`}
              >
                {m.label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
