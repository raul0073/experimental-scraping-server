"use client";

/** WHAT COUNTS AS A GOOD MANAGER — AND YOU DECIDE.
 *
 *  The same argument the ratings boards make, applied one level up. A fixed
 *  manager ranking is an opinion with a number on it; a configurable one
 *  invites the disagreement and shows its working. The budget is the part
 *  that makes it honest: every config spends exactly 100 and no more, so a
 *  weighting is a set of TRADE-OFFS rather than a wish list — you cannot
 *  decide that everything matters most.
 *
 *  Only DIRECTIONAL metrics appear here. The fingerprint cannot be weighted
 *  and has no slider, because a short first substitution is not better than a
 *  late one and a slider would assert that it is.
 */

import { BUDGET } from "./scoreUi";
import { HintBox, HintIcon } from "./Hint";
import {
  type Metric,
  dimensionLabel,
} from "./contract";

export function WeightEditor({
  directional,
  weights,
  setWeight,
  reset,
  dirty,
  open,
  setOpen,
}: {
  directional: Metric[];
  weights: Record<string, number>;
  setWeight: (key: string, value: number) => void;
  reset: () => void;
  /** whether anything has been changed from the defaults — the reset button
   *  is pointless before that and misleading after it is pressed */
  dirty: boolean;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const spent = directional.reduce((a, m) => a + (weights[m.key] ?? 0), 0);

  // Dimensions in the order the payload declares them, so the panel follows
  // the metric bank rather than an alphabet.
  const dims: string[] = [];
  for (const m of directional) if (!dims.includes(m.dimension)) dims.push(m.dimension);

  return (
    <section className="mt-4 rounded-xl border border-line bg-card">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-line px-3 py-3 sm:px-4">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="flex items-baseline gap-1.5 text-left text-[14px] font-semibold hover:text-home"
        >
          <span className="text-ink-3">{open ? "▾" : "▸"}</span>
          What counts as a good manager — and you decide
        </button>
        <span className="num text-[12.5px]">
          <span
            className={
              spent === BUDGET
                ? "font-semibold text-good"
                : "font-semibold text-[#9a7400]"
            }
          >
            {spent}
          </span>
          <span className="text-ink-3"> / {BUDGET}</span>
        </span>
        {dirty && (
          <button
            onClick={reset}
            className="ml-auto rounded-md border border-line px-2 py-0.5 text-[11.5px] text-ink-2 transition-colors hover:border-ink-3 hover:text-ink"
          >
            back to defaults
          </button>
        )}
      </div>

      {open && (
        <div className="p-3 sm:p-4">
          <p className="mb-1 text-[12px] leading-relaxed text-ink-2">
            Move a slider and the table re-sorts under your hand — the
            percentiles are already computed, so the browser is only taking a
            weighted mean of them. Your weights are kept in this browser and
            survive a refresh; nothing is sent anywhere.
          </p>
          <p className="mb-3 text-[12px] leading-relaxed text-ink-3">
            The defaults are a starting point and nothing more. They are not a
            claim about what management is, which is the question this panel
            exists to hand back to you.
          </p>

          <div className="grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {dims.map((d) => (
              <div
                key={d}
                className="rounded-lg border border-line bg-[#fcfcfd] p-2.5"
              >
                <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">
                  {dimensionLabel(d)}
                </div>
                {directional
                  .filter((m) => m.dimension === d)
                  .map((m) => {
                    const w = weights[m.key] ?? 0;
                    return (
                      <div key={m.key} className="mt-2">
                        <div className="group/hint relative flex items-baseline justify-between gap-2">
                          <span className="flex min-w-0 items-baseline gap-1 text-[12.5px] text-ink-2">
                            <span className="truncate">{m.label}</span>
                            {m.invert && (
                              <span
                                className="shrink-0 text-[11px] text-ink-3"
                                title="lower is better"
                              >
                                ↓
                              </span>
                            )}
                            <HintIcon />
                          </span>
                          <span className="num text-[11.5px] text-ink-3">{w}</span>
                          <HintBox>
                            {m.help || m.label}
                            {m.invert && (
                              <>
                                {" "}
                                <b className="text-ink">Lower is better</b>, so
                                the percentile is turned over before it is
                                weighted.
                              </>
                            )}
                          </HintBox>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={30}
                          value={w}
                          aria-label={`${m.label} weight`}
                          onChange={(e) => setWeight(m.key, Number(e.target.value))}
                          className="w-full accent-[#4a7ba6]"
                        />
                      </div>
                    );
                  })}
              </div>
            ))}
          </div>

          <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
            Spend the whole hundred or spend less — the score is the weighted
            mean of what you did spend, so leaving budget on the table changes
            nothing except how many things you are judging on. A metric a
            manager has no data for is dropped and the rest renormalised,
            rather than filled in at average; the score cell says when that
            happened.
          </p>
        </div>
      )}
    </section>
  );
}
