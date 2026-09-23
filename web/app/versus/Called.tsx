"use client";

import type { Fixture, Outcome } from "@/lib/data";

/** THE SHIPPED MODEL'S ANSWER, at the top of the fixture it is about.
 *
 *  This page used to be a place you navigated to and chose two clubs. It is
 *  now the page a fixture opens onto, and the first thing on it has to be
 *  the prediction the rest of the site publishes — a number with no working
 *  shown is the least trustworthy thing we have, and everything below here
 *  is the working.
 *
 *  TWO MODELS, AND THEY WILL DISAGREE. The projection further down this page
 *  is computed live from the process Elo; this is the shipped model from the
 *  weekly export. They are independent, and the honest thing is to show both
 *  and label which is which rather than quietly pick one. Agreement is
 *  evidence. Disagreement is information — and hiding it would be the only
 *  way to get it wrong.
 */

const STYLE: Record<Outcome, { chip: string; bar: string; label: string }> = {
  home: { chip: "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]", bar: "#2f6fae", label: "home win" },
  draw: { chip: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]", bar: "#c9a227", label: "draw" },
  away: { chip: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]", bar: "#c2572a", label: "away win" },
};

const ORDER: Outcome[] = ["home", "draw", "away"];

/** The rule that can override the highest probability, and the reason it is
 *  worth saying out loud on the page rather than only in the code.
 *
 *  A pure argmax essentially never says draw — draws top out around a third
 *  while a win side spreads past that — so the call takes a draw once the
 *  calibrated draw probability reaches 0.32. It was swept on 194 graded
 *  rows, which is not many, and re-testing it is the first thing on the list
 *  once the other four leagues are on disk. Until then a reader deserves to
 *  know when the call is not simply the biggest number. */
const DRAW_FLOOR = 32;

export function Called({ f, league }: { f: Fixture; league: string }) {
  const top = ORDER.reduce((a, b) => (f.p[b] > f.p[a] ? b : a), "home" as Outcome);
  const overridden = f.call === "draw" && top !== "draw";

  return (
    <section className="rounded-xl border border-line bg-card p-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-[11px] uppercase tracking-[0.14em] text-ink-3">
          What the model expects
        </h2>
        <span className="text-[11.5px] text-ink-3">
          {league.split("-")[1] ?? league} · {f.date}
        </span>
        <span
          className={`ml-auto inline-block rounded-full border px-2.5 py-0.5 text-[12px] font-semibold ${STYLE[f.call].chip}`}
        >
          calls it a {STYLE[f.call].label}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3">
        {ORDER.map((o) => {
          const called = f.call === o;
          return (
            <div
              key={o}
              className={`rounded-lg border p-3 ${
                called ? "border-ink-3 bg-[#fafbfc]" : "border-line"
              }`}
            >
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                {o === "home" ? f.home : o === "away" ? f.away : "draw"}
              </div>
              <div className="num mt-0.5 text-[24px] font-bold leading-none text-ink">
                {Math.round(f.p[o])}%
              </div>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#eef1f3]">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${f.p[o]}%`, background: STYLE[o].bar }}
                />
              </div>
              <div className="num mt-1.5 text-[11.5px] text-ink-3">
                fair {f.fair[o].toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[12.5px] text-ink-2">
        <span>
          likeliest score <b className="num text-ink">{f.score}</b>
        </span>
        <span>
          expected goals{" "}
          <b className="num text-ink">
            {f.xg[0].toFixed(2)} – {f.xg[1].toFixed(2)}
          </b>
        </span>
      </div>

      {overridden && (
        <p className="mt-3 rounded-lg border border-[#e4d49a] bg-[#fdf8e7] p-2.5 text-[12px] leading-relaxed text-[#6b5606]">
          <b>The call is not the highest number here.</b>{" "}
          {o(top)} is on {Math.round(f.p[top])}% against {Math.round(f.p.draw)}%
          for the draw, but the model states a draw once that probability
          reaches {DRAW_FLOOR}% — because a pure pick-the-biggest almost never
          says draw, and roughly a quarter of matches are drawn. The
          probabilities above are untouched by that rule; only this one word
          is.
        </p>
      )}
    </section>
  );

  function o(k: Outcome) {
    return k === "home" ? f.home : k === "away" ? f.away : "The draw";
  }
}
