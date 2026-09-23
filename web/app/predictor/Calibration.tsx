"use client";

import type { RecordData } from "@/lib/data";
import { setStored, useStored } from "@/lib/useStored";

/** The site's one claim, at the top of the page that makes it.
 *
 *  🐛 THE OLD VERSION PRINTED HALF A COMPARISON. Each bucket showed "said
 *  36.8% · n=70" in small grey type and "41.4%" in a big bold one — so the
 *  number the eye lands on is the one that means nothing on its own, and the
 *  claim (these two are close) had to be reconstructed by reading two
 *  differently-sized numbers and subtracting. Calibration IS the comparison;
 *  drawing one of the two values large and the other as a caption hides
 *  exactly the thing being asserted.
 *
 *  So each bucket is now two bars on a shared 0–100 track. Close bars mean
 *  an honest probability and you see it without arithmetic. It also fixes
 *  the five-into-four-columns wrap that left the last bucket orphaned on its
 *  own row, because rows stack instead of tiling.
 *
 *  THIN BUCKETS ARE DIMMED RATHER THAN DROPPED. The 70–80% bucket has six
 *  observations and lands at 100%, which in a grid of equal cards shouts
 *  louder than the n=70 bucket beside it. Six of six is not evidence of
 *  anything, but hiding it would be picking which of our own numbers to
 *  show — so it stays, faded, and says so.
 *
 *  COLLAPSIBLE, AND THE SUMMARY SURVIVES COLLAPSE. Someone who comes back
 *  every week wants the fixtures, not the methodology, but the headline —
 *  how many calls, what they averaged, what landed — is one line and is the
 *  reason to trust the table underneath. That line stays in the header.
 */
const KEY = "predictorous:calibration-open";

/** Below this many observations a bucket is noise wearing a percentage. */
const THIN = 20;

function Bar({
  pct, tone, label, value,
}: {
  pct: number; tone: "said" | "landed"; label: string; value: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[46px] shrink-0 text-right text-[10.5px] text-ink-3">
        {label}
      </span>
      <div className="h-[7px] flex-1 overflow-hidden rounded-full bg-[#eef0f2]">
        <div
          className={`h-full rounded-full ${
            tone === "said" ? "bg-[#b9d5e8]" : "bg-[#1c5b8a]"
          }`}
          style={{ width: `${Math.max(1, Math.min(100, pct))}%` }}
        />
      </div>
      <span
        className={`num w-[44px] shrink-0 text-right text-[11.5px] ${
          tone === "landed" ? "font-semibold text-ink" : "text-ink-3"
        }`}
      >
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

export function Calibration({ record }: { record: RecordData }) {
  /** Open by default: it is the claim the table underneath rests on, so a
   *  first-time reader should meet it. A reader who shuts it has said they
   *  came for the fixtures, and that sticks. */
  const open = useStored(KEY, "1") === "1";
  const toggle = () => setStored(KEY, open ? "0" : "1");

  const { graded, hit_rate, said_avg, calibration } = record;
  if (!calibration?.length) return null;

  return (
    <section className="rounded-xl border border-line bg-card">
      <button
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3.5 text-left"
      >
        <h2 className="text-[13px] font-semibold uppercase tracking-wider text-ink-3">
          The only claim that matters
        </h2>

        {/* The headline outlives the collapse: it is the reason to believe
            the table below, and it is one line. */}
        <span className="num flex flex-wrap items-center gap-x-2.5 text-[12px] text-ink-2">
          <span>
            <b className="font-semibold text-ink">{graded}</b> graded
          </span>
          {said_avg !== null && (
            <>
              <span className="text-ink-3">·</span>
              <span>
                said <b className="font-semibold text-ink">{said_avg}%</b>
              </span>
            </>
          )}
          {hit_rate !== null && (
            <>
              <span className="text-ink-3">·</span>
              <span>
                landed <b className="font-semibold text-ink">{hit_rate}%</b>
              </span>
            </>
          )}
        </span>

        <span className="ml-auto text-[11px] text-ink-3">
          {open ? "hide ▴" : "show ▾"}
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-5 pb-5 pt-4">
          <p className="max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
            Anyone can publish predictions. The test is whether the stated
            probabilities are honest: when this model says 45%, does it happen
            about 45% of the time? Each row is a band of confidence — the pale
            bar is what we said, the solid bar is what actually happened.
          </p>

          <div className="mt-4 space-y-3.5">
            {calibration.map((b) => {
              const thin = b.n < THIN;
              return (
                <div
                  key={b.bucket}
                  className={thin ? "opacity-45" : undefined}
                  title={
                    thin
                      ? `${b.n} observations — too few to read anything into`
                      : undefined
                  }
                >
                  <div className="mb-1 flex items-baseline gap-2">
                    <span className="num text-[12px] font-semibold text-ink">
                      {b.bucket}
                    </span>
                    <span className="num text-[11px] text-ink-3">
                      n={b.n}
                    </span>
                    {thin && (
                      <span className="text-[10.5px] uppercase tracking-wider text-ink-3">
                        too thin to read
                      </span>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Bar pct={b.said} tone="said" label="said" value={b.said} />
                    <Bar
                      pct={b.landed}
                      tone="landed"
                      label="landed"
                      value={b.landed}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <p className="mt-4 text-[12px] leading-relaxed text-ink-3">
            Buckets are the model&apos;s stated probability for the outcome it
            called. A model that is confident and wrong shows up here as a
            solid bar far short of its pale one — which is why this is the
            first thing on the page rather than a methodology footnote.
          </p>
        </div>
      )}
    </section>
  );
}
