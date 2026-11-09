import Link from "next/link";

/** The page for a URL that is not one of ours — and for the three routes
 *  that exist only in development (admin, betting, lab), which the static
 *  export resolves to this page on purpose.
 *
 *  It says where the real things are rather than apologising. A reader who
 *  typed a stale link wants the predictor or the record, not a paragraph
 *  about the error; the metadata keeps it out of search results. */
export const metadata = {
  title: "Not found",
  robots: { index: false, follow: false },
};

const PLACES = [
  {
    href: "/",
    label: "Next round",
    what: "every fixture in the big five, priced, with the fair price of each result",
  },
  {
    href: "/predictor/history",
    label: "Track record",
    what: "every call committed before kickoff, graded, misses included",
  },
  {
    href: "/predictor/market",
    label: "Versus the market",
    what: "the model scored against the bookmakers' closing prices",
  },
  {
    href: "/ratings",
    label: "Ratings",
    what: "players, sides and managers, measured on what they do",
  },
  {
    href: "/how-it-works",
    label: "How it works",
    what: "from shots to a published probability, and what never gets in",
  },
];

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl py-6 sm:py-12">
      <p className="num text-[12px] uppercase tracking-[0.14em] text-ink-3">
        404
      </p>
      <h1 className="font-display mt-2 text-[26px] tracking-[0.01em]">
        There is no page here.
      </h1>
      <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
        Either the address is wrong or it points at something this site does
        not publish. Nothing has been removed from the record: every call ever
        made is still on it, including the ones that missed. These are the
        pages that exist.
      </p>

      <ul className="mt-6 divide-y divide-line rounded-xl border border-line bg-card">
        {PLACES.map((p) => (
          <li key={p.href}>
            <Link
              href={p.href}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-4 py-3 transition-colors hover:bg-[#f4f6f8]"
            >
              <span className="text-[14px] font-semibold text-ink">{p.label}</span>
              <span className="text-[12.5px] text-ink-3">{p.what}</span>
            </Link>
          </li>
        ))}
      </ul>

      <p className="mt-6 text-[12.5px] text-ink-3">
        Probabilities and fair prices only — never betting advice.
      </p>
    </div>
  );
}
