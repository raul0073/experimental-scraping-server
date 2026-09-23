"use client";

/** A HELP POPOVER THAT CANNOT PUSH THE PAGE SIDEWAYS.
 *
 *  The site's shared `Info` is a fixed 288px box anchored to its own icon. In
 *  a table header with room to the right that is exactly right, and it is
 *  used unchanged there. In a stack of narrow rows on a phone it is not: the
 *  icon sits after a label, so the box starts 130-odd pixels in and runs off
 *  a 375px screen by about ninety. An absolutely positioned element that
 *  overflows the document adds horizontal scroll to the whole page, and a
 *  ranking you have to swipe left and right to read is not a ranking anyone
 *  reads.
 *
 *  So this one is anchored to the ROW rather than to the icon — `inset-x-0`
 *  against a positioned row makes the popover exactly as wide as the row it
 *  explains, at any viewport, with no arithmetic and nothing to get wrong. It
 *  also means the whole row is the hover target instead of a 14px circle,
 *  which is the difference between reachable and not on a touch screen.
 *
 *  The caller owns the row and adds `group/hint relative` to it; the named
 *  group keeps this from firing on every other `group-hover` on the page.
 */

export function HintIcon() {
  return (
    <span
      aria-hidden
      className="ml-0.5 inline-flex h-3.5 w-3.5 shrink-0 cursor-help items-center justify-center rounded-full border border-ink-3 text-[9px] font-semibold not-italic leading-none text-ink-3 transition-colors group-hover/hint:border-home group-hover/hint:text-home"
    >
      i
    </span>
  );
}

export function HintBox({ children }: { children: React.ReactNode }) {
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute inset-x-0 top-full z-30 mt-1.5 rounded-lg border border-line bg-card p-2.5 text-left text-[11.5px] font-normal normal-case leading-relaxed tracking-normal text-ink-2 opacity-0 shadow-lg transition-opacity duration-100 group-hover/hint:opacity-100"
    >
      {children}
    </span>
  );
}
