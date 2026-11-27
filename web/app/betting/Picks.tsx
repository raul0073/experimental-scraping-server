"use client";

import {
  Fragment,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { leagueShort } from "@/lib/league";
import { setStored, useStored } from "@/lib/useStored";

import { getWeekly, message } from "./api";

/** THE PICKS TAB — what the model says about this round, and the form built
 *  from it.
 *
 *  DEVELOPMENT ONLY, AND NOT BECAUSE OF ANYTHING IN THIS FILE. The guard that
 *  matters is `notFound()` in layout.tsx, which stops the segment being
 *  emitted at all — no HTML, no chunk, nothing to find. The `DEV` check at
 *  the bottom is a second belt in the same spirit as app/admin/page.tsx; on
 *  its own it would still ship this component's JavaScript.
 *
 *  A CLIENT COMPONENT ON PURPOSE. The payload is fetched at RUNTIME from the
 *  local API, never at build time. A server component would bake this round's
 *  picks into the exported HTML, which is the one outcome the section exists
 *  to avoid: no betting payload may reach the static export or
 *  web/public/data, both of which are published wholesale.
 *
 *  EVERY PRICE HERE IS A FAIR PRICE — 1/p, computed from the probability
 *  beside it. No bookmaker's number is fetched, shown or compared against,
 *  which is why each one is labelled: a column of decimals next to a football
 *  fixture reads as odds unless it says otherwise. page.tsx states the rule
 *  once at the top; this file keeps it.
 */
const DEV = process.env.NODE_ENV === "development";

/** THE TYPES COME FROM THE FUNCTION, NOT FROM A NAME. Deriving everything
 *  from `getWeekly`'s return type means this file keeps compiling whatever
 *  api.ts calls its interfaces, and fails loudly if the SHAPE ever stops
 *  matching — which is the only change that should break a view. */
type Weekly = Awaited<ReturnType<typeof getWeekly>>;
type Fixture = Weekly["all_predictions"][string][number];
type Pick = Weekly["draw_picks"][number];
/** The watchlist is NOT a Pick, and the types say so: no rank, no pick_type,
 *  because it is never ranked and never committed. */
type Watch = NonNullable<Weekly["draw_watchlist"]>[number];
type Sheet = NonNullable<Pick["sheet"]>;
type SideSheet = Sheet["home"];
type FormRecord = SideSheet["venue"];
type FormGame = SideSheet["last8"][number];
type Probs = Fixture["probabilities"];
type Side = keyof Probs;
type Strategy = NonNullable<Weekly["strategy"]>;
type Slip = Strategy["slip"];
type Leg = Slip["legs"][number];

const SIDES: { key: Side; mark: string; label: string }[] = [
  { key: "home", mark: "1", label: "home" },
  { key: "draw", mark: "X", label: "draw" },
  { key: "away", mark: "2", label: "away" },
];

const MARK: Record<Side, string> = { home: "1", draw: "X", away: "2" };

const SIDE_STYLE: Record<Side, string> = {
  home: "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]",
  draw: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  away: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
};

/** Tier is not a verdict on the pick, it is where the model's best number for
 *  the fixture sat: gold ≥55%, silver ≥45%, flip below. A flip-tier DRAW pick
 *  is normal rather than a contradiction — 33% is a strong draw and still
 *  nobody's favourite, and that is exactly why the draw board exists. */
const TIER_STYLE: Record<string, string> = {
  gold: "bg-[#f6efd6] text-[#6b5606] border-[#e0cf93]",
  silver: "bg-[#eef0f2] text-[#55606b] border-[#d8dde1]",
  flip: "bg-[#f7f8f9] text-[#8a949e] border-line",
};

const TIER_TITLE: Record<string, string> = {
  gold: "gold — the model's best number for this fixture is 55% or more",
  silver: "silver — best number between 45% and 55%",
  flip: "flip — no outcome reaches 45%",
};

// ---------------------------------------------------------------- formatting

const pct = (p: number, dp = 1) => `${(p * 100).toFixed(dp)}%`;

/** FAIR PRICE. The decimal a probability is worth at breakeven — 1/p — and
 *  nothing else. Never an offered price, because none is fetched. */
const fairStr = (p: number) => (p > 0 ? (1 / p).toFixed(2) : "—");

/** "2026-10-10" → "Sat 10 Oct". Forced to UTC and en-GB: kickoffs are plain
 *  dates, and letting the browser apply a local timezone turns a Saturday
 *  fixture into Friday for every reader west of London. */
function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

const xgPair = (xg: Record<string, number>) =>
  Object.values(xg)
    .map((v) => v.toFixed(2))
    .join(" – ");

const fixtureKey = (f: { league: string; home: string; away: string }) =>
  `${f.league}|${f.home}|${f.away}`;

// ------------------------------------------------------------- small pieces

function Mark({ side, big = false }: { side: Side; big?: boolean }) {
  return (
    <span
      title={`Winner mark ${MARK[side]} — ${side}`}
      className={`inline-block rounded-full border text-center font-semibold ${
        SIDE_STYLE[side]
      } ${
        big
          ? "min-w-[30px] px-2.5 py-0.5 text-[15px]"
          : "min-w-[22px] px-2 py-0.5 text-[11.5px]"
      }`}
    >
      {MARK[side]}
    </span>
  );
}

function Tier({ tier }: { tier: string }) {
  return (
    <span
      title={TIER_TITLE[tier] ?? tier}
      className={`inline-block rounded-full border px-2 py-px text-[10.5px] font-semibold uppercase tracking-wider ${
        TIER_STYLE[tier] ?? TIER_STYLE.flip
      }`}
    >
      {tier}
    </span>
  );
}

/** A Hebrew form name sitting inside an English sentence. `dir="auto"`
 *  isolates it so the bidi algorithm cannot drag the surrounding punctuation
 *  into the Hebrew run — without it "שיטה 2/4," renders with the comma on the
 *  wrong end of the name. */
function He({ children }: { children: React.ReactNode }) {
  return (
    <span dir="auto" className="inline-block">
      {children}
    </span>
  );
}

function Section({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-[19px] tracking-[0.01em]">{title}</h2>
      {lede && (
        <p className="mt-1.5 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          {lede}
        </p>
      )}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function SubHead({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[13px] font-semibold uppercase tracking-wider text-ink-3">
      {children}
    </h3>
  );
}

/** THE FULL TRIPLET, ALWAYS. A pick shown as one percentage is an assertion;
 *  the same pick shown against the other two outcomes is a reading of the
 *  match that somebody can disagree with. Each tile carries the probability
 *  and the fair price it implies. */
function Triplet({
  p,
  call,
  highlight,
}: {
  p: Probs;
  call?: Side;
  highlight?: Side;
}) {
  return (
    <div className="grid grid-cols-3 gap-1.5">
      {SIDES.map(({ key, mark, label }) => {
        const v = p[key];
        const on = highlight ? key === highlight : call === key;
        return (
          <div
            key={key}
            title={`${label} — ${pct(v)}, fair price ${fairStr(v)}`}
            className={`rounded-lg border px-1 py-1 text-center ${
              on ? SIDE_STYLE[key] : "border-line bg-[#fafbfc] text-ink-2"
            }`}
          >
            <div className="text-[10px] font-semibold uppercase tracking-wider opacity-70">
              {mark}
            </div>
            <div className="num text-[15px] font-semibold leading-tight">
              {pct(v, 0)}
            </div>
            <div className="num text-[11px] leading-tight opacity-75">
              {fairStr(v)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------ 1. the window

/** WHICH ROUND IS THIS? FIVE ANSWERS.
 *
 *  The betting window is one span of dates, but the leagues inside it are on
 *  different gameweeks — today La Liga is on 8 while the Bundesliga is on 5.
 *  "This gameweek" is five numbers, so the page prints all five rather than
 *  choosing one and being wrong about four. */
function WindowStrip({
  w,
  onReload,
  busy,
}: {
  w: Weekly;
  onReload: () => void;
  busy: boolean;
}) {
  const win = w.window;
  const weeks = w.weeks ?? {};
  const names = Object.keys(weeks);

  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="num text-[15px]">
          {win ? (
            <>
              <span className="font-semibold">{day(win.start)}</span>
              <span className="text-ink-3"> → </span>
              <span className="font-semibold">{day(win.end)}</span>
            </>
          ) : (
            <span className="text-ink-3">no open window</span>
          )}
        </div>
        <div className="num flex items-baseline gap-3 text-[12px] text-ink-3">
          <span>season {w.season}</span>
          {w.generated_at && (
            <span>
              generated {w.generated_at.slice(0, 16).replace("T", " ")}Z
            </span>
          )}
          <button
            onClick={onReload}
            disabled={busy}
            className="cursor-pointer text-home underline underline-offset-2 disabled:opacity-50"
          >
            {busy ? "loading" : "refresh"}
          </button>
        </div>
      </div>

      {w.booked && (
        <p className="mt-3 rounded-lg border border-line bg-[#fafbfc] px-3 py-2 text-[12px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink-1">
            This round is booked.
          </span>{" "}
          Everything below is the ledger record for window{" "}
          <span className="num">{w.booked}</span> — the games it was committed
          on, at the prices they were committed at, with results filled in as
          they land. It will not change while the round is live, which is the
          point: a form you have already filled in cannot be re-picked. The
          next round opens once this one fully grades.
        </p>
      )}

      {names.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {names.map((lg) => (
            <span
              key={lg}
              className="flex items-baseline gap-1.5 rounded-full border border-line bg-[#fafbfc] px-2.5 py-1 text-[12px]"
            >
              <span className="text-ink-2">{leagueShort(lg)}</span>
              <span className="num font-semibold">
                wk {(weeks[lg] ?? []).join(" / ") || "—"}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------- 2. the picks

/** One pick, with everything needed to argue with it.
 *
 *  THE TICKET NUMBER IS THE TRIPLET'S NUMBER. Since 2026-11-20 every pick
 *  is ranked on the published probability of its side, so the figure on the
 *  card, the triplet beside it and the fair price the ledgers freeze are one
 *  number. Before that, draw picks were ranked on the form arm's classifier
 *  alone and could sit a couple of points off the triplet (Torino v Udinese
 *  was 33.4% on the ticket against 31.1% in the triplet), which is why the
 *  card still states the pick probability as its own figure and flags a
 *  divergence: rows booked under the old ranking keep their old number.
 */
function PickCard({ p, rank }: { p: Pick; rank: number }) {
  const side: Side = p.pick_type;
  const prob = p.pick_prob;
  const inTriplet = p.probabilities[side];
  // a hair of rounding is not a disagreement; half a point is
  const diverges = Math.abs(inTriplet - prob) >= 0.005;

  return (
    <li className="rounded-xl border border-line bg-card p-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="num text-[11px] text-ink-3">#{rank}</span>
            <Mark side={side} />
            <Tier tier={p.tier} />
          </div>
          <div className="mt-1.5 text-[15px] font-medium leading-snug">
            {p.home} <span className="text-ink-3">v</span> {p.away}
          </div>
          <div className="num mt-0.5 text-[11.5px] text-ink-3">
            {leagueShort(p.league)} · wk {p.week} · {day(p.kickoff)}
            {p.confidence === "low" && (
              <span className="text-[#a34a22]"> · low confidence</span>
            )}
          </div>
          {/* A committed pick whose fixture has been played. The result is
              stated next to the pick rather than on a separate page, because
              mid-round the only question worth answering about a booked leg
              is whether it came in. */}
          {p.score && (
            <div className="num mt-1.5 flex items-baseline gap-1.5 text-[11.5px]">
              <span className="font-semibold">{p.score}</span>
              <span
                className={
                  p.hit
                    ? "rounded-full bg-[#e8f3ec] px-1.5 py-0.5 font-semibold text-[#1f6b3d]"
                    : "rounded-full bg-[#f6eaea] px-1.5 py-0.5 font-semibold text-[#8a2b2b]"
                }
              >
                {p.hit ? "landed" : "missed"}
              </span>
            </div>
          )}
        </div>

        {/* The probability the pick was ranked on, and the fair price it is
            worth. The price is the number a real slip gets checked against,
            so it sits under the percentage rather than a column away. */}
        <div className="shrink-0 text-right">
          <div className="num text-[22px] font-semibold leading-none">
            {pct(prob)}
          </div>
          <div className="num text-[11.5px] text-ink-3">
            fair price {fairStr(prob)}
          </div>
        </div>
      </div>

      <div className="mt-3">
        <Triplet p={p.probabilities} highlight={side} />
      </div>

      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[11.5px] text-ink-3">
        <span className="num">xG {xgPair(p.xg)}</span>
        {diverges && (
          <span
            className="num"
            title={
              `ranked on ${pct(prob)} — this row was booked before 2026-11-20, ` +
              `when the ticket ranked on the form arm's draw classifier. ` +
              `The published triplet has ${pct(inTriplet)}; new picks rank on it.`
            }
          >
            ticket {pct(prob)} · triplet {pct(inTriplet)}
          </span>
        )}
      </div>
      <FormSheet sheet={p.sheet} />
    </li>
  );
}

/** Every hit pattern of a k-of-n system at the model's probabilities: what
 *  it pays at the book's prices and at fair. Pure; shared by every board. */
function bookMath(
  legs: { prob: number; fair: number }[],
  prices: (number | null)[],
  k: number,
) {
  const n = legs.length;
  const price = (i: number) => prices[i] ?? legs[i].fair;
  const lines: number[][] = [];
  const pick = (start: number, acc: number[]) => {
    if (acc.length === k) {
      lines.push([...acc]);
      return;
    }
    for (let i = start; i < n; i++) pick(i + 1, [...acc, i]);
  };
  pick(0, []);
  const stake = lines.length;
  let evBook = 0;
  let evFair = 0;
  let pProfitBook = 0;
  let pProfitFair = 0;
  let pAnyBook = 0;
  // by number of legs landed: probability, and the return at book averaged
  // over which legs they were (prices differ, so it is an average)
  const byHits: { p: number; ret: number }[] = Array.from({ length: n + 1 }, () => ({ p: 0, ret: 0 }));
  for (let mask = 0; mask < 1 << n; mask++) {
    let p = 1;
    let hits = 0;
    for (let i = 0; i < n; i++) {
      const on = (mask & (1 << i)) !== 0;
      p *= on ? legs[i].prob : 1 - legs[i].prob;
      if (on) hits++;
    }
    let rb = 0;
    let rf = 0;
    for (const line of lines) {
      if (line.every((i) => mask & (1 << i))) {
        rb += line.reduce((m, i) => m * price(i), 1);
        rf += line.reduce((m, i) => m * legs[i].fair, 1);
      }
    }
    evBook += p * rb;
    evFair += p * rf;
    if (rb > stake) pProfitBook += p;
    if (rf > stake) pProfitFair += p;
    if (rb > 0) pAnyBook += p;
    byHits[hits].p += p;
    byHits[hits].ret += p * rb;
  }
  for (const h of byHits) h.ret = h.p > 0 ? h.ret / h.p : 0;
  const maxBook = lines.reduce((s, line) => s + line.reduce((m, i) => m * price(i), 1), 0);
  const maxFair = lines.reduce((s, line) => s + line.reduce((m, i) => m * legs[i].fair, 1), 0);
  return { stake, lines: lines.length, maxBook, maxFair, evBook, evFair, pProfitBook, pProfitFair, pAnyBook, byHits };
}

/** "YOUR BOOK PAYS", on every board. The user bets systems and accumulators,
 *  so a leg's price only matters through the whole ticket: one shaded leg
 *  taxes every line it sits in. Per board the user types each leg's price
 *  as the book shows it (fair is the placeholder), picks the structure
 *  (k of n: 1 = singles, n = one accumulator, the Winner שיטה in between),
 *  and gets the whole ticket's numbers at those prices against at fair,
 *  and a verdict. Prices are kept per board and window in the browser;
 *  nothing is sent anywhere and no odds are ingested. */
/** Winner's own names for a ticket of k picks from n, so the buttons read
 *  the way the slip does: סינגלים for each leg on its own, שיטה k/n for
 *  every k-combination, and the one-line accumulator by its Hebrew name. */
const FOLD_HE: Record<number, string> = {
  2: "כפולה", 3: "שלישייה", 4: "רביעייה", 5: "חמישייה", 6: "שישייה", 7: "שביעייה", 8: "שמינייה",
};
function structureName(k: number, n: number): string {
  if (k === 1) return "סינגלים";
  if (k === n) return FOLD_HE[n] ?? `${n}-fold`;
  return `שיטה ${k}/${n}`;
}
function structureHelp(k: number, n: number): string {
  if (k === 1) return `${n} separate bets, one on each pick`;
  if (k === n) return `one bet on all ${n} picks together; pays only if every one lands`;
  return `every combination of ${k} of the ${n} picks, each combination a separate line; pays from ${k} hits`;
}

function BoardBook({ legs, defaultK, store }: { legs: Pick[]; defaultK: number; store: string }) {
  const n = legs.length;
  const rawPrices = useStored(`${store}.prices`, "{}");
  const rawK = useStored(`${store}.k`, "");
  let saved: Record<string, string> = {};
  try {
    saved = JSON.parse(rawPrices) as Record<string, string>;
  } catch {
    saved = {};
  }
  const k = Math.min(n, Math.max(1, Number(rawK) || Math.min(defaultK, n)));
  const prices = legs.map((l) => {
    const v = Number(saved[fixtureKey(l)]);
    return Number.isFinite(v) && v > 1 ? v : null;
  });
  const typed = prices.filter((p) => p !== null).length;
  const m = bookMath(
    legs.map((l) => ({ prob: l.pick_prob, fair: 1 / l.pick_prob })),
    prices,
    k,
  );
  const ev = (m.evBook - m.stake) / m.stake;
  const set = (key: string, v: string) => setStored(`${store}.prices`, JSON.stringify({ ...saved, [key]: v }));
  const structure = structureName(k, n);
  return (
    <div className="mt-2 rounded-lg border border-line bg-[#fafbfb] p-3 text-[12px] text-ink-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-medium text-ink">Your book pays</span>
        <span className="flex items-baseline gap-1.5 text-ink-3">
          structure
          {Array.from({ length: n }, (_, i) => i + 1).map((kk) => (
            <button
              key={kk}
              onClick={() => setStored(`${store}.k`, String(kk))}
              className={`num rounded border px-1.5 py-0.5 ${
                kk === k ? "border-ink bg-card text-ink" : "border-line text-ink-3"
              }`}
              title={structureHelp(kk, n)}
            >
              {structureName(kk, n)}
            </button>
          ))}
        </span>
      </div>
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {legs.map((l, i) => (
          <label key={fixtureKey(l)} className="flex items-baseline justify-between gap-2">
            <span className="truncate">
              <span className="num text-ink-3">{l.pick_type === "home" ? "1" : l.pick_type === "draw" ? "X" : "2"}</span>{" "}
              {l.home} v {l.away}
            </span>
            <span className="num flex items-baseline gap-1.5 text-ink-3">
              fair {(1 / l.pick_prob).toFixed(2)}
              <input
                inputMode="decimal"
                placeholder={(1 / l.pick_prob).toFixed(2)}
                value={saved[fixtureKey(l)] ?? ""}
                onChange={(e) => set(fixtureKey(l), e.target.value)}
                className="num w-16 rounded border border-line bg-card px-1.5 py-0.5 text-[12px] text-ink"
              />
              {prices[i] !== null && (
                <span className={prices[i]! >= 1 / l.pick_prob ? "text-[#1f6b3d]" : "text-[#8a2b2b]"}>
                  {pct(prices[i]! * l.pick_prob)}
                </span>
              )}
            </span>
          </label>
        ))}
      </div>
      <div className="num mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2">
        <span>
          {structure} · {m.lines} line{m.lines === 1 ? "" : "s"} ·{" "}
          {k === n ? "total odds" : "max win (every line lands)"}{" "}
          <b className="font-semibold text-ink">{m.maxBook.toFixed(2)}</b>
          {typed > 0 && <span className="text-ink-3"> (fair {m.maxFair.toFixed(2)})</span>}
          {k === n && <span className="text-ink-3"> · lands {pct(m.pAnyBook)}</span>}
        </span>
        <span>
          expected return{" "}
          <b className={`font-semibold ${ev >= 0 ? "text-[#1f6b3d]" : "text-[#8a2b2b]"}`}>
            {ev >= 0 ? "+" : ""}
            {(ev * 100).toFixed(0)}%
          </b>
          {typed > 0 && (
            <span className="text-ink-3">
              {" "}
              (fair {m.evFair >= m.stake ? "+" : ""}
              {(((m.evFair - m.stake) / m.stake) * 100).toFixed(0)}%)
            </span>
          )}
        </span>
        <span>
          week in profit <b className="font-semibold text-ink">{pct(m.pProfitBook)}</b>
          {typed > 0 && <span className="text-ink-3"> (fair {pct(m.pProfitFair)})</span>}
        </span>
        <span>
          anything back <b className="font-semibold text-ink">{pct(m.pAnyBook)}</b>
        </span>
        {typed > 0 && typed < n && <span className="text-ink-3">{n - typed} leg(s) still at fair</span>}
      </div>
      {/* the week, hit by hit: this is what "38% anything back" means -
          the chance of each count of legs landing and what that returns
          on the stake. No adding percentages across rows. */}
      <div className="num mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-3">
        {m.byHits.map((h, hits) => (
          <span key={hits}>
            {hits} land{hits === 1 ? "s" : ""}{" "}
            <b className="font-semibold text-ink">{pct(h.p)}</b> →{" "}
            <b className={`font-semibold ${h.ret > m.stake ? "text-[#1f6b3d]" : h.ret > 0 ? "text-[#7a5a00]" : "text-ink-3"}`}>
              {h.ret.toFixed(1)}
            </b>
            <span> on {m.stake}</span>
          </span>
        ))}
      </div>
      <Verdict ev={ev} typed={typed > 0} />
    </div>
  );
}

function PickGroup({
  title,
  note,
  picks,
  book,
}: {
  title: string;
  note: string;
  picks: Pick[];
  /** Attach "your book pays" to this board: the default structure (k of n)
   *  and a storage key for the typed prices. */
  book?: { defaultK: number; store: string };
}) {
  return (
    <div className="mt-5 first:mt-0">
      <div className="flex flex-wrap items-baseline gap-x-2.5">
        <SubHead>{title}</SubHead>
        <span className="num text-[12px] text-ink-3">{picks.length}</span>
      </div>
      <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-ink-2">
        {note}
      </p>
      {picks.length === 0 ? (
        <p className="mt-2 text-[12.5px] text-ink-3">none this window.</p>
      ) : (
        <ul className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {picks.map((p, i) => (
            <PickCard key={fixtureKey(p)} p={p} rank={p.rank ?? i + 1} />
          ))}
        </ul>
      )}
      {book && picks.length >= 1 && (
        <BoardBook legs={picks} defaultK={book.defaultK} store={book.store} />
      )}
    </div>
  );
}

// ------------------------------------------------------- 3. the Winner form

function Banker({ b }: { b: NonNullable<Strategy["banker"]> }) {
  const side: Side = b.side;
  return (
    <div className="rounded-xl border border-line bg-[#fafbfc] p-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <SubHead>Banker</SubHead>
        <span className="num text-[11.5px] text-ink-3">
          {leagueShort(b.league)} · {day(b.kickoff)}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Mark side={side} big />
        <span className="text-[15px] font-medium">{b.fixture}</span>
      </div>
      <div className="num mt-1.5 flex flex-wrap items-baseline gap-x-3 text-[12.5px]">
        <span className="font-semibold">{b.team}</span>
        <span>{pct(b.prob)}</span>
        <span className="text-ink-3">fair price {fairStr(b.prob)}</span>
        {b.tier && <Tier tier={b.tier} />}
      </div>
      {/* strategy_advisor.py is blunt about this and the page should be too:
          a banker form is an upgrade only when the leg is OFFERED above its
          fair price — a comparison this page cannot make, because it holds no
          offered prices. So the anchor is shown and explicitly not
          recommended. */}
      <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
        The anchor leg: the strongest certified in-window favourite (≥55%) not
        already used as a draw leg, multiplied into every line of a banker
        form. It is a <b>price</b> tool, never a default — a banker shape only
        becomes the better bet when that leg is offered above its fair price,
        and no offered price exists anywhere on this page.
      </p>
    </div>
  );
}

function LegRow({ l }: { l: Leg }) {
  const side: Side = l.mark === "X" ? "draw" : l.mark === "2" ? "away" : "home";
  return (
    <tr className="border-t border-line">
      <td className="py-2 pl-3 pr-2">
        <Mark side={side} />
      </td>
      <td className="py-2 pr-3">
        <div className="text-[13px]">{l.fixture}</div>
        <div className="num text-[11px] text-ink-3">
          {l.league} · {day(l.kickoff)}
          {l.team ? ` · ${l.team}` : ""}
        </div>
      </td>
      <td className="px-2 py-2 text-[11px] uppercase tracking-wider text-ink-3">
        {l.role}
      </td>
      <td className="num px-2 py-2 text-right text-[13px] font-semibold">
        {pct(l.prob)}
      </td>
      {/* The leg's own fair price as the advisor froze it, not recomputed
          here — so a slip on screen reads exactly as the slip in the book. */}
      <td className="num py-2 pl-2 pr-3 text-right text-[13px]">
        {l.breakeven.toFixed(2)}
      </td>
    </tr>
  );
}

/** THE HIT TABLE — the part that stops a form being a promise.
 *
 *  system_scenarios() enumerates every hit subset and prices the winning
 *  lines at each leg's FAIR price, which turns "not every win is a gain" into
 *  a number instead of a warning: on a 2/5, two legs landing wins one line of
 *  ten and hands back a fraction of the outlay. Each row says how likely that
 *  hit count is, how many lines it wins, and what comes back as a multiple of
 *  the WHOLE stake. */
function Scenarios({ slip }: { slip: Slip }) {
  if (slip.scenarios.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
            <th className="py-2 pl-3 pr-2 text-left font-semibold">Hits</th>
            <th className="px-2 py-2 text-right font-semibold">Chance</th>
            <th className="px-2 py-2 text-right font-semibold">Lines won</th>
            <th
              className="px-2 py-2 text-right font-semibold"
              title="average return as a multiple of the total stake, every line priced at its legs' fair prices"
            >
              Back
            </th>
            <th className="py-2 pl-2 pr-3 text-left font-semibold">Result</th>
          </tr>
        </thead>
        <tbody>
          {slip.scenarios.map((s) => (
            <tr
              key={s.hits}
              className={`border-t border-line ${s.profit ? "bg-[#f3f9f4]" : ""}`}
            >
              <td className="num py-2 pl-3 pr-2 font-semibold">
                {s.hits} of {slip.legs.length}
              </td>
              <td className="num px-2 py-2 text-right">{pct(s.p)}</td>
              <td className="num px-2 py-2 text-right text-ink-2">
                {s.lines_won} / {s.total_lines}
              </td>
              <td className="num px-2 py-2 text-right">
                {s.ret_frac > 0 ? `×${s.ret_frac.toFixed(2)}` : "—"}
              </td>
              <td className="py-2 pl-2 pr-3 text-[12px]">
                {s.profit ? (
                  <span className="font-semibold text-good">profit</span>
                ) : s.lines_won > 0 ? (
                  <span className="text-[#6b5606]">part refund</span>
                ) : (
                  <span className="text-ink-3">nothing</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** WHAT IT WAS CHOSEN OVER — because a recommendation with no alternatives
 *  shown is an assertion.
 *
 *  These are the other structures the advisor built over THESE SAME legs,
 *  each scored by exact P(profit). The two probability columns are the whole
 *  point: P(return) is the chance something comes back, P(profit) is the
 *  chance more comes back than went out. On the recommended 2/4 they are one
 *  number; on the 2/5 they are 71% and 34%, and a form chosen on the first
 *  column would be chosen on a figure that counts losing weeks as wins. */
function Alternatives({ slip }: { slip: Slip }) {
  const alts = slip.alternatives ?? [];
  if (alts.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
            <th className="py-2 pl-3 pr-2 text-left font-semibold">Form</th>
            <th className="px-2 py-2 text-right font-semibold">Lines</th>
            <th
              className="px-2 py-2 text-right font-semibold"
              title="chance at least one line comes back"
            >
              P(return)
            </th>
            <th
              className="px-2 py-2 text-right font-semibold"
              title="chance the return beats the stake"
            >
              P(profit)
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-line bg-[#f3f9f4]">
            <td className="py-2 pl-3 pr-2">
              <He>{slip.title_he}</He>
              <span className="ml-2 rounded-full border border-[#b7dcbf] bg-[#e7f4ea] px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-good">
                recommended
              </span>
              <div className="text-[11.5px] text-ink-2">{slip.title_en}</div>
            </td>
            <td className="num px-2 py-2 text-right">{slip.lines}</td>
            <td className="num px-2 py-2 text-right">{pct(slip.p_return)}</td>
            <td className="num px-2 py-2 text-right font-semibold">
              {pct(slip.p_profit)}
            </td>
          </tr>
          {alts.map((a) => (
            <tr key={a.title_en} className="border-t border-line">
              <td className="py-2 pl-3 pr-2">
                <He>{a.title_he}</He>
                <div className="text-[11.5px] text-ink-2">{a.title_en}</div>
              </td>
              <td className="num px-2 py-2 text-right">{a.lines}</td>
              <td className="num px-2 py-2 text-right text-ink-2">
                {pct(a.p_return)}
              </td>
              <td className="num px-2 py-2 text-right">{pct(a.p_profit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The Winner catalog over the same four draws — Yankee, Lucky 15, Trixi,
 *  banker × system. A DIFFERENT question from `alternatives` above (which
 *  re-ranks structures the advisor itself would commit to), so it is a
 *  separate list rather than more rows in that table. */
function Options({ options }: { options: Strategy["options"] }) {
  if (options.length === 0) return null;
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {options.map((o) => (
        <li key={o.name} className="rounded-xl border border-line bg-card p-3">
          <div dir="auto" className="text-[13px] font-medium">
            {o.name}
          </div>
          <div className="num mt-1 flex flex-wrap gap-x-3 text-[12px] text-ink-2">
            <span>{o.lines} lines</span>
            <span title="chance at least one line comes back">
              return {pct(o.p_return)}
            </span>
            <span title="the tail: three or more legs landing">
              3+ {pct(o.p_big)}
            </span>
          </div>
          <p className="mt-1 text-[11.5px] leading-relaxed text-ink-3">
            {o.note}
          </p>
        </li>
      ))}
    </ul>
  );
}

/** THE SLIP AT THE BOOK'S PRICES. A system pays every winning line at the
 *  product of ITS legs' prices, so one shaded leg taxes every line it sits
 *  in and the only honest number is the whole ticket's. The user types each
 *  leg's price as the book shows it (fair is the placeholder); the board
 *  enumerates every hit pattern at the model's probabilities and reports
 *  the max win, the expected return and the chance of ending the week up,
 *  at those prices against at fair. Prices are kept per window in the
 *  browser; nothing is sent anywhere and no odds are ingested. */
function SlipBook({ slip }: { slip: Slip }) {
  const key = `betting.slip.book.${slip.legs.map((l) => l.fixture).join("|")}`;
  const raw = useStored(key, "{}");
  let saved: Record<string, string> = {};
  try {
    saved = JSON.parse(raw) as Record<string, string>;
  } catch {
    saved = {};
  }
  const legs = slip.legs;
  const k = slip.k;
  const prices = legs.map((l) => {
    const v = Number(saved[l.fixture]);
    return Number.isFinite(v) && v > 1 ? v : null;
  });
  const typed = prices.filter((p) => p !== null).length;
  const price = (i: number) => prices[i] ?? legs[i].breakeven;

  // every hit pattern, lines won, return at book and at fair
  const n = legs.length;
  const lines: number[][] = [];
  const pick = (start: number, acc: number[]) => {
    if (acc.length === k) {
      lines.push([...acc]);
      return;
    }
    for (let i = start; i < n; i++) pick(i + 1, [...acc, i]);
  };
  pick(0, []);
  const stake = lines.length;
  let evBook = 0;
  let evFair = 0;
  let pProfitBook = 0;
  let pProfitFair = 0;
  for (let mask = 0; mask < 1 << n; mask++) {
    let p = 1;
    for (let i = 0; i < n; i++) p *= mask & (1 << i) ? legs[i].prob : 1 - legs[i].prob;
    let rb = 0;
    let rf = 0;
    for (const line of lines) {
      if (line.every((i) => mask & (1 << i))) {
        rb += line.reduce((m, i) => m * price(i), 1);
        rf += line.reduce((m, i) => m * legs[i].breakeven, 1);
      }
    }
    evBook += p * rb;
    evFair += p * rf;
    if (rb > stake) pProfitBook += p;
    if (rf > stake) pProfitFair += p;
  }
  const maxBook = lines.reduce((s, line) => s + line.reduce((m, i) => m * price(i), 1), 0);
  const maxFair = lines.reduce((s, line) => s + line.reduce((m, i) => m * legs[i].breakeven, 1), 0);

  const set = (fixture: string, v: string) => {
    const next = { ...saved, [fixture]: v };
    setStored(key, JSON.stringify(next));
  };

  return (
    <div className="mt-3 rounded-lg border border-line bg-[#fafbfb] p-3 text-[12px] text-ink-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-medium text-ink">At your book&apos;s prices</span>
        <span className="text-ink-3">
          type each leg as the book shows it; blank means fair
        </span>
      </div>
      <div className="mt-2 grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {legs.map((l) => (
          <label key={l.fixture} className="flex items-baseline justify-between gap-2">
            <span className="truncate">
              <span className="num text-ink-3">{l.mark}</span> {l.fixture}
            </span>
            <span className="num flex items-baseline gap-1.5 text-ink-3">
              fair {l.breakeven.toFixed(2)}
              <input
                inputMode="decimal"
                placeholder={l.breakeven.toFixed(2)}
                value={saved[l.fixture] ?? ""}
                onChange={(e) => set(l.fixture, e.target.value)}
                className="num w-16 rounded border border-line bg-card px-1.5 py-0.5 text-[12px] text-ink"
              />
            </span>
          </label>
        ))}
      </div>
      <div className="num mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2">
        <span>
          {stake} lines · max win{" "}
          <b className="font-semibold text-ink">{maxBook.toFixed(1)}</b>
          {typed > 0 && <span className="text-ink-3"> (fair {maxFair.toFixed(1)})</span>}
        </span>
        <span>
          expected return{" "}
          <b className={`font-semibold ${evBook >= stake ? "text-[#1f6b3d]" : "text-[#8a2b2b]"}`}>
            {evBook >= stake ? "+" : ""}
            {(((evBook - stake) / stake) * 100).toFixed(0)}%
          </b>
          {typed > 0 && (
            <span className="text-ink-3">
              {" "}
              (fair {evFair >= stake ? "+" : ""}
              {(((evFair - stake) / stake) * 100).toFixed(0)}%)
            </span>
          )}
        </span>
        <span>
          week in profit{" "}
          <b className="font-semibold text-ink">{pct(pProfitBook)}</b>
          {typed > 0 && <span className="text-ink-3"> (fair {pct(pProfitFair)})</span>}
        </span>
        {typed > 0 && typed < n && (
          <span className="text-ink-3">{n - typed} leg(s) still at fair</span>
        )}
      </div>
      <Verdict ev={(evBook - stake) / stake} typed={typed > 0} />
    </div>
  );
}

/** ONE WORD, because that is what the user asked for. The rule is law 5 of
 *  the betting skill: a ticket is worth taking iff, at the model's own
 *  probabilities, the book's prices return at least the stake. Within five
 *  points under is "marginal": the model's strongest calls have run a few
 *  points ahead of their stated odds, draws have not, so marginal on a
 *  favourites ticket is a maybe and marginal on draws is a pass. Below that,
 *  no structure rescues it (law 5 again: systems reshape variance, they do
 *  not create value from negative legs). */
function Verdict({ ev, typed }: { ev: number; typed: boolean }) {
  if (!typed) {
    return (
      <p className="mt-2 text-[12px] text-ink-3">
        Verdict waits for the book&apos;s prices. At fair this ticket is a
        coin at even money; every shaded leg moves it below that.
      </p>
    );
  }
  const take = ev >= 0;
  const marginal = !take && ev >= -0.05;
  return (
    <p
      className={`mt-2 rounded-md px-2.5 py-1.5 text-[12.5px] font-medium ${
        take
          ? "bg-[#e8f3ec] text-[#1f6b3d]"
          : marginal
            ? "bg-[#fbf3d5] text-[#7a5a00]"
            : "bg-[#f6eaea] text-[#8a2b2b]"
      }`}
    >
      {take
        ? `Take it: the book pays at least fair, ${(ev * 100).toFixed(0) === "0" ? "level" : `+${(ev * 100).toFixed(0)}%`} expected on the stake.`
        : marginal
          ? `Marginal: ${(ev * 100).toFixed(0)}% expected. Only if these are favourites, which have run ahead of their stated odds; on draws, pass.`
          : `Pass: ${(ev * 100).toFixed(0)}% expected at these prices. No structure turns shaded legs into value.`}
    </p>
  );
}

function WinnerForm({ s }: { s: Strategy }) {
  const slip = s.slip;
  const legs = slip.legs;
  const profitFrom = slip.scenarios.find((x) => x.profit)?.hits;

  return (
    <div>
      {/* The board first: the structure choice is downstream of how good the
          draw board is this week, and board_avg against the ~32% ceiling is
          the figure the advisor actually decides on. */}
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-xl border border-line bg-card px-4 py-3">
        <span className="text-[12px] uppercase tracking-wider text-ink-3">
          Draw board
        </span>
        <span className="text-[17px] font-semibold capitalize">{s.board}</span>
        <span className="num text-[12.5px] text-ink-2">
          top-4 average {pct(s.board_avg)} against a ~32% ceiling
        </span>
        {slip.mandate && (
          <span
            className="ml-auto rounded-full border border-line bg-[#fafbfc] px-2.5 py-0.5 text-[11.5px] text-ink-2"
            title="this pot bets one instrument; everything else is an alternative to swap into on price"
          >
            mandate: {slip.mandate}
          </span>
        )}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="rounded-xl border border-line bg-card p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <div>
              <div className="font-display text-[20px] tracking-[0.01em]">
                <He>{slip.title_he}</He>
              </div>
              <div className="text-[12.5px] text-ink-2">{slip.title_en}</div>
            </div>
            <div className="num text-right text-[12px] text-ink-3">
              <div>
                system {slip.k}/{legs.length} · {slip.lines} lines
              </div>
              <div>
                profit from {profitFrom ?? "—"} hits ·{" "}
                <span className="font-semibold text-ink">
                  {pct(slip.p_profit)}
                </span>{" "}
                of weeks
              </div>
            </div>
          </div>

          <p className="mt-2 text-[12.5px] leading-relaxed text-ink-2">
            {slip.how}
          </p>

          <div className="mt-3 overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-3 pr-2 text-left font-semibold">
                    Mark
                  </th>
                  <th className="py-2 pr-3 text-left font-semibold">Fixture</th>
                  <th className="px-2 py-2 text-left font-semibold">Role</th>
                  <th className="px-2 py-2 text-right font-semibold">Prob</th>
                  <th
                    className="py-2 pl-2 pr-3 text-right font-semibold"
                    title="1/p — the breakeven decimal the probability is worth. Not an offered price."
                  >
                    Fair price
                  </th>
                </tr>
              </thead>
              <tbody>
                {legs.map((l) => (
                  <LegRow key={`${l.mark}-${l.fixture}`} l={l} />
                ))}
              </tbody>
            </table>
          </div>

          <p className="num mt-2 text-[11.5px] text-ink-3">
            {slip.lines} lines — every {slip.k}-combination of the{" "}
            {legs.length} legs. A line that lands pays the product of its
            legs&apos; fair prices, against {slip.lines} units staked.
          </p>
          <SlipBook slip={slip} />
        </div>

        <div className="space-y-3">
          {s.banker && <Banker b={s.banker} />}
          <Scenarios slip={slip} />
        </div>
      </div>

      <div className="mt-5">
        <SubHead>Chosen over</SubHead>
        <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-ink-2">
          The same legs in every other structure the advisor built, ranked by
          the chance of ending the week up. <b>P(return)</b> is the chance
          something comes back; <b>P(profit)</b> is the chance more comes back
          than went out — on a 2/5 those are two very different numbers, and
          only the second one is a reason to choose a form.
        </p>
        <div className="mt-2">
          <Alternatives slip={slip} />
        </div>
      </div>

      <div className="mt-5">
        <SubHead>Catalog shapes for this board</SubHead>
        <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-ink-2">
          The standard Winner forms over the same draws, for comparison —
          structures only, every line valued at fair price.
        </p>
        <div className="mt-2">
          <Options options={s.options} />
        </div>
      </div>

      {/* The advisor's own words, verbatim. It carries the mandate, why
          pure-favourite forms are excluded, and that prices and stakes are
          the reader's department. Paraphrasing would only put a second voice
          on the same decision. */}
      {s.text && (
        <p className="mt-5 max-w-4xl rounded-xl border border-line bg-[#fafbfc] p-4 text-[12.5px] leading-relaxed text-ink-2">
          {s.text}
        </p>
      )}
    </div>
  );
}

// -------------------------------------------------------- 4. how many land

/** THE EXPECTATION-SETTER, SET LARGE ON PURPOSE.
 *
 *  Four draws at about a third each is a board that looks generous and
 *  resolves harshly: the likeliest single week is ONE of the four landing,
 *  and all four is a 1-in-87 week. These three numbers are the honest frame
 *  around every pick above them, so they get the biggest type on the page
 *  rather than a footnote under it.
 *
 *  The tie to the form is exact rather than rhetorical: a 2/4 over these legs
 *  profits precisely when at least two land, so P(≥2) IS the recommended
 *  form's profit-week figure. Said only when the shape actually matches —
 *  hence the `profitFrom === 2` guard, not a hardcoded sentence. */
function Trixy({
  trixy,
  n,
  profitFrom,
}: {
  trixy: NonNullable<Weekly["trixy"]>;
  n: number;
  profitFrom?: number;
}) {
  const tiles = [
    { k: "at least 2", p: trixy.p_ge2, note: "the money-back zone" },
    { k: "at least 3", p: trixy.p_ge3, note: "the tail that pays" },
    { k: `all ${n}`, p: trixy.p_4of4, note: "the week nobody plans for" },
  ];
  return (
    <div>
      <div className="grid gap-2 sm:grid-cols-3">
        {tiles.map((t) => (
          <div
            key={t.k}
            className="rounded-xl border border-line bg-card px-4 py-3.5"
          >
            <div className="text-[11.5px] uppercase tracking-wider text-ink-3">
              {t.k} of {n}
            </div>
            <div className="num mt-0.5 text-[30px] font-semibold leading-none">
              {pct(t.p)}
            </div>
            <div className="mt-1 text-[11.5px] text-ink-3">{t.note}</div>
          </div>
        ))}
      </div>
      {profitFrom === 2 && (
        <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-ink-2">
          The recommended form profits from two legs landing, so{" "}
          <span className="num font-semibold">{pct(trixy.p_ge2)}</span> is the
          same number as its profit-week figure — not a coincidence, the same
          event counted once.
        </p>
      )}
    </div>
  );
}

// ------------------------------------------------------ the candidate pool

const FORM_TONE: Record<FormGame["r"], string> = {
  W: "bg-[#e8f3ec] text-[#1f6b3d]",
  D: "bg-[#fbf3d5] text-[#7a5a00]",
  L: "bg-[#f6eaea] text-[#8a2b2b]",
};

/** THE RESULTS-PAGE NUMBERS, next to the candidate. On 2026-11-20 a tie
 *  between two draw candidates was settled by opening a stats site: home
 *  record at home, away record away, draws this season, the last eight with
 *  scores, goals a game. All of it is on disk, so it now rides with every
 *  draw candidate and the watchlist.
 *
 *  SHOWN, NOT RANKED ON. experiment_draw_window measured the same day that
 *  reading draw rate and goal volume over eight matches, or by venue,
 *  predicts draws no better than the classifier's own 38-match window, and
 *  that the eight-match venue split is measurably worse. The sheet is for a
 *  human comparing two candidates the model has level, which is the one
 *  place these numbers earned their keep. Closed by default so the board
 *  stays a board. */
function FormSheet({ sheet }: { sheet?: Sheet | null }) {
  if (!sheet) return null;
  const sides: [string, SideSheet][] = [
    ["at home", sheet.home],
    ["away", sheet.away],
  ];
  const gpg = (v: number | null) => (v == null ? "—" : v.toFixed(1));
  const wdl = (r: FormRecord) => (
    <span className="num">
      <b className="font-semibold text-[#1f6b3d]">{r.w}</b>-
      <b className="font-semibold text-[#7a5a00]">{r.d}</b>-
      <b className="font-semibold text-[#8a2b2b]">{r.l}</b>
    </span>
  );
  // a plain render helper, not a component: a component created during
  // render remounts on every render (react-hooks/static-components)
  const row = (label: string, cell: (s: SideSheet) => ReactNode) => (
    <tr key={label} className="border-t border-line">
      <td className="py-1 pr-2 text-ink-3">{label}</td>
      {sides.map(([where, s]) => (
        <td key={where} className="num py-1 pr-2">
          {cell(s)}
        </td>
      ))}
    </tr>
  );
  return (
    <details open className="mt-2 text-[11.5px] text-ink-2">
      <summary className="num cursor-pointer select-none text-ink-3">
        form
        {sheet.through && <> · results through {sheet.through}</>}
      </summary>
      <table className="mt-1.5 w-full border-collapse text-[11.5px]">
        <thead>
          <tr>
            <th className="w-[26%] py-1 pr-2 text-left font-normal text-ink-3"> </th>
            {sides.map(([where, s]) => (
              <th key={where} className="py-1 pr-2 text-left font-medium text-ink">
                {s.team} <span className="font-normal text-ink-3">{where}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {row("this season, there", (s) => (
              <>
                {wdl(s.venue)} <span className="text-ink-3">in {s.venue.gp}</span> · {s.venue.gf}:{s.venue.ga} ·{" "}
                {s.venue.ppg.toFixed(2)} ppg
              </>
            ))}
          {row("this season, all", (s) => (
              <>
                {wdl(s.overall)} · {s.overall.gf}:{s.overall.ga} · draws{" "}
                <b className="font-semibold text-ink">{pct(s.overall.draw_pct)}</b>
              </>
            ))}
          {row("last 8", (s) => (
              <>
                <b className="font-semibold text-ink">{s.last8_draws}</b> draw{s.last8_draws === 1 ? "" : "s"} ·{" "}
                <b className="font-semibold text-ink">{gpg(s.last8_goals_pg)}</b> goals a game
              </>
            ))}
          {row("newest first", (s) => (
              <span className="flex flex-wrap gap-1">
                {[...s.last8].reverse().map((g) => (
                  <span
                    key={`${g.date}-${g.opp}`}
                    className={`num rounded px-1.5 py-0.5 ${FORM_TONE[g.r]}`}
                    title={`${g.date} · ${g.at === "H" ? "home v" : "away at"} ${g.opp}`}
                  >
                    <span className="opacity-60">{g.at}</span> {g.gf}-{g.ga}
                  </span>
                ))}
              </span>
            ))}
        </tbody>
      </table>
    </details>
  );
}

/** THE POOL THE FOUR CAME FROM. draw_candidates is the top 8: the first four
 *  are the ticket and get ledger-graded, 5-8 exist so a better-priced
 *  alternate can be swapped in by hand. Only the ones past the ticket are
 *  listed here — the first four are the section above, and printing them
 *  twice would make the board look twice as deep as it is. */
function Candidates({ rows }: { rows: Pick[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
            <th className="py-2 pl-3 pr-2 text-left font-semibold">#</th>
            <th className="py-2 pr-3 text-left font-semibold">Fixture</th>
            <th className="px-2 py-2 text-left font-semibold">League</th>
            <th className="px-2 py-2 text-left font-semibold">Kickoff</th>
            <th className="px-2 py-2 text-center font-semibold">Tier</th>
            <th className="px-2 py-2 text-right font-semibold">Draw</th>
            <th className="py-2 pl-2 pr-3 text-right font-semibold">
              Fair price
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <Fragment key={fixtureKey(p)}>
              <tr className="border-t border-line">
                <td className="num py-2 pl-3 pr-2 text-ink-3">{p.rank}</td>
                <td className="py-2 pr-3">
                  {p.home} <span className="text-ink-3">v</span> {p.away}
                </td>
                <td className="px-2 py-2 text-[12px] text-ink-2">
                  {leagueShort(p.league)}
                </td>
                <td className="num px-2 py-2 text-[12px] text-ink-2">
                  {day(p.kickoff)}
                </td>
                <td className="px-2 py-2 text-center">
                  <Tier tier={p.tier} />
                </td>
                <td className="num px-2 py-2 text-right font-semibold">
                  {pct(p.pick_prob)}
                </td>
                <td className="num py-2 pl-2 pr-3 text-right">
                  {fairStr(p.pick_prob)}
                </td>
              </tr>
              {p.sheet && (
                <tr>
                  <td colSpan={7} className="px-3 pb-2 pt-0">
                    <FormSheet sheet={p.sheet} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** SHOWN, NEVER PICKED. Low-confidence fixtures whose draw number would
 *  otherwise be ticket-grade. prediction_service.py keeps them out of the
 *  ledger because the probability rests on league-average priors rather than
 *  on these teams — so they are published for the reader's judgement and
 *  excluded from the ticket, and the page has to be clear which of those two
 *  things it is doing. Dashed border, because it is not a pick. */
function Watchlist({ rows }: { rows: Watch[] }) {
  if (rows.length === 0) return null;
  return (
    <ul className="grid gap-2 sm:grid-cols-3">
      {rows.map((p) => (
        <li
          key={fixtureKey(p)}
          className="rounded-xl border border-dashed border-[#e4d49a] bg-[#fffdf5] p-3"
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[13.5px] font-medium">
              {p.home} <span className="text-ink-3">v</span> {p.away}
            </span>
            <span className="num text-[14px] font-semibold">
              {pct(p.pick_prob)}
            </span>
          </div>
          <div className="num mt-0.5 text-[11.5px] text-ink-3">
            {leagueShort(p.league)} · wk {p.week} · {day(p.kickoff)} · fair
            price {fairStr(p.pick_prob)}
          </div>
          <FormSheet sheet={p.sheet} />
        </li>
      ))}
    </ul>
  );
}

// -------------------------------------------------------- 5. every fixture

type Marked = { side: Side; rank: number; type: Side };

const KEY_LEAGUE = "predictorous:league";

/** EVERY FIXTURE IN THE WINDOW, league by league.
 *
 *  THE PICKS ARE THE TOP OF THIS LIST, NOT A SEPARATE CLAIM. Ten picks with
 *  no denominator cannot be argued with; the same ten sitting inside the 48
 *  fixtures they were chosen from can. Picked rows carry their mark and rank,
 *  so the question a reader actually has — why is THAT one not on the ticket
 *  — is answered by reading across the row.
 *
 *  AND THE GATES ARE PRINTED, because they are not guessable from the
 *  numbers. prediction_service.py's pick() takes only normal-confidence,
 *  in-window fixtures, walks down by probability, and SKIPS any fixture whose
 *  home or away team is already on the board — a doubled team correlates legs
 *  the system maths assumes are independent. So a 34% draw can be passed over
 *  while a 32% is taken, and with that rule off screen it reads as a bug.
 *
 *  Table on a laptop, cards below `sm` — the pattern RoundTables set. Eleven
 *  columns at 375px pushes the team names off the left edge, which is the one
 *  column the rest is meaningless without. Nothing is dropped between the two
 *  renderings. */
function AllFixtures({
  all,
  marked,
}: {
  all: Weekly["all_predictions"];
  marked: Map<string, Marked>;
}) {
  const names = Object.keys(all);
  const first = names[0] ?? "";
  /** Same storage key as the front page's round tables: somebody who follows
   *  one league follows it here too, and making them re-pick per page is the
   *  failure that key was introduced to fix. A stored league missing from
   *  this payload falls back rather than rendering an empty section. */
  const stored = useStored(KEY_LEAGUE, first);
  const active = names.includes(stored) ? stored : first;

  if (names.length === 0) return null;

  const rows = [...(all[active] ?? [])].sort((a, b) =>
    a.kickoff === b.kickoff
      ? a.home.localeCompare(b.home)
      : a.kickoff.localeCompare(b.kickoff),
  );

  return (
    <div>
      <div role="tablist" className="flex flex-wrap gap-2">
        {names.map((lg) => {
          const on = lg === active;
          return (
            <button
              key={lg}
              role="tab"
              aria-selected={on}
              onClick={() => setStored(KEY_LEAGUE, lg)}
              className={`flex cursor-pointer items-baseline gap-1.5 rounded-full border px-2.5 py-1.5 text-[12.5px] transition-colors sm:px-3.5 sm:text-[13px] ${
                on
                  ? "border-ink bg-ink text-white"
                  : "border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink"
              }`}
            >
              <span className={on ? "font-medium" : undefined}>
                {leagueShort(lg)}
              </span>
              <span
                className={`num text-[11px] ${on ? "text-white/60" : "text-ink-3"}`}
              >
                {all[lg].length}
              </span>
            </button>
          );
        })}
      </div>

      {/* ==================================================== phone: cards */}
      <ul className="mt-3 space-y-2 sm:hidden">
        {rows.map((f) => {
          const m = marked.get(fixtureKey(f));
          return (
            <li
              key={fixtureKey(f)}
              className={`rounded-xl border bg-card p-3 ${
                m ? "border-ink-3" : "border-line"
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="num text-[11.5px] text-ink-3">
                  wk {f.week} · {day(f.kickoff)}
                </span>
                <span className="flex items-center gap-1.5">
                  {m && (
                    <span className="num text-[10.5px] font-semibold uppercase tracking-wider text-ink-2">
                      {m.type} #{m.rank}
                    </span>
                  )}
                  <Mark side={f.call} />
                  <Tier tier={f.tier} />
                </span>
              </div>
              <div className="mt-1 text-[14px]">
                {f.home} <span className="text-ink-3">v</span> {f.away}
              </div>
              <div className="mt-2">
                <Triplet p={f.probabilities} call={f.call} />
              </div>
              <div className="num mt-1.5 flex flex-wrap justify-between gap-x-3 text-[11px] text-ink-3">
                <span>xG {xgPair(f.xg)}</span>
                <span>
                  {f.confidence === "low" && (
                    <span className="text-[#a34a22]">low confidence · </span>
                  )}
                  {f.in_window ? "in window" : "out of window"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {/* =================================================== laptop: table */}
      <div className="mt-3 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-2 text-left font-semibold">Date</th>
              <th className="px-2 py-2 text-right font-semibold">Wk</th>
              <th className="py-2 pr-2 text-right font-semibold">Home</th>
              <th className="py-2 pl-2 text-left font-semibold">Away</th>
              <th className="px-3 py-2 text-center font-semibold">Call</th>
              {SIDES.map((s) => (
                <th
                  key={s.key}
                  className="px-3 py-2 text-center font-semibold"
                  title={`${s.label} — probability, and the fair price beneath`}
                >
                  {s.mark}
                </th>
              ))}
              <th className="px-2 py-2 text-center font-semibold">Tier</th>
              <th className="px-2 py-2 text-right font-semibold">xG</th>
              <th className="py-2 pl-2 pr-4 text-left font-semibold">
                On the board
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const m = marked.get(fixtureKey(f));
              return (
                <tr
                  key={fixtureKey(f)}
                  className={`border-t border-line ${m ? "bg-[#fafbfc]" : ""}`}
                >
                  <td className="num whitespace-nowrap py-2.5 pl-4 pr-2 text-[12px] text-ink-3">
                    {day(f.kickoff)}
                  </td>
                  <td className="num px-2 py-2.5 text-right text-[12px] text-ink-3">
                    {f.week}
                  </td>
                  <td className="py-2.5 pr-2 text-right">{f.home}</td>
                  <td className="py-2.5 pl-2">{f.away}</td>
                  <td className="px-3 py-2.5 text-center">
                    <Mark side={f.call} />
                  </td>
                  {SIDES.map((s) => {
                    const v = f.probabilities[s.key];
                    const on = f.call === s.key;
                    return (
                      <td
                        key={s.key}
                        className={`px-3 py-2.5 text-center ${on ? "bg-[#f7f8f9]" : ""}`}
                      >
                        <div
                          className={`num text-[14px] ${
                            on ? "font-semibold text-ink" : "text-ink-2"
                          }`}
                        >
                          {pct(v, 0)}
                        </div>
                        <div className="num text-[11.5px] text-ink-3">
                          {fairStr(v)}
                        </div>
                      </td>
                    );
                  })}
                  <td className="px-2 py-2.5 text-center">
                    <Tier tier={f.tier} />
                  </td>
                  <td className="num whitespace-nowrap px-2 py-2.5 text-right text-[12px] text-ink-3">
                    {xgPair(f.xg)}
                  </td>
                  <td className="whitespace-nowrap py-2.5 pl-2 pr-4 text-[11.5px]">
                    {m ? (
                      <span className="flex items-center gap-1.5">
                        <Mark side={m.side} />
                        <span className="text-ink-2">
                          {m.type} #{m.rank}
                        </span>
                      </span>
                    ) : f.confidence === "low" ? (
                      <span
                        className="text-[#a34a22]"
                        title="low confidence — ineligible for the ticket, because the xG rests on league-average priors"
                      >
                        low confidence
                      </span>
                    ) : !f.in_window ? (
                      <span className="text-ink-3">out of window</span>
                    ) : (
                      <span className="text-ink-3">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-ink-3">
        How a fixture gets on the board: normal confidence, inside the window,
        then ranked by probability — and skipped if either team is already on
        that board, because the system maths treats legs as independent and a
        doubled team correlates them. A higher number can therefore be passed
        over for a lower one.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------- the tab

export function Picks() {
  const [w, setW] = useState<Weekly | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /** The fetch and the "busy" flag are split so the mount effect can start
   *  the fetch without setting state synchronously — the loading line below
   *  already covers the first load, and `busy` is for the reload button. */
  const fetchRound = useCallback(
    () =>
      getWeekly().then(
        (next) => {
          setW(next);
          setErr(null);
          setBusy(false);
        },
        (e: unknown) => {
          setErr(message(e));
          setBusy(false);
        },
      ),
    [],
  );
  const load = useCallback(() => {
    setBusy(true);
    return fetchRound();
  }, [fetchRound]);

  useEffect(() => {
    void fetchRound();
  }, [fetchRound]);

  /** Second belt only — layout.tsx is the guard that matters, and it keeps
   *  this route out of a production build entirely. */
  if (!DEV) return null;

  if (err) {
    return (
      <div>
        <p className="rounded-lg border border-[#eec4ab] bg-[#fae5d9] px-3 py-2 text-[12.5px] text-[#a34a22]">
          {err}
        </p>
        <button
          onClick={load}
          disabled={busy}
          className="mt-2 cursor-pointer text-[12.5px] text-home underline underline-offset-2 disabled:opacity-50"
        >
          try again
        </button>
      </div>
    );
  }

  if (!w) {
    return <p className="text-[13px] text-ink-3">loading this round…</p>;
  }

  const draws = w.draw_picks;
  const homes = w.home_win_picks;
  const aways = w.away_win_picks ?? [];
  const candidates = w.draw_candidates;
  const watchlist = w.draw_watchlist ?? [];
  const strategy = w.strategy;
  const profitFrom = strategy?.slip.scenarios.find((s) => s.profit)?.hits;

  /** One lookup so the full fixture list can flag its own picked rows. Built
   *  FROM the pick lists rather than re-deriving the selection, which would
   *  be a second implementation of the gates and would drift from the first
   *  one the day either changes. */
  const marked = new Map<string, Marked>();
  for (const list of [draws, homes, aways]) {
    list.forEach((p, i) => {
      marked.set(fixtureKey(p), {
        side: p.pick_type,
        rank: p.rank ?? i + 1,
        type: p.pick_type,
      });
    });
  }

  return (
    <div>
      <WindowStrip w={w} onReload={load} busy={busy} />

      {/* THE ADVISOR'S CALL, FIRST. The rule (user decision 2026-11-27) in
          one box: only draws at 30%+ make the ticket, four play שיטה 2/4,
          three play as singles, fewer sit the week out. The rest of the tab
          is the evidence; this is the decision. */}
      <div
        className={`mt-4 rounded-xl border px-4 py-3 ${
          draws.length >= 3
            ? "border-[#cfe3d6] bg-[#eef7f1]"
            : "border-[#e4d49a] bg-[#fdf8e7]"
        }`}
      >
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-[11px] uppercase tracking-wider text-ink-3">
            The advisor
          </span>
          <span className="text-[16px] font-semibold">
            {draws.length >= 4
              ? "Four draws qualify → שיטה 2/4, six lines"
              : draws.length === 3
                ? "Three draws qualify → three singles"
                : `${draws.length === 0 ? "No" : draws.length} draw${draws.length === 1 ? "" : "s"} qualify → no bet this week`}
          </span>
          {strategy && (
            <span className="num text-[12.5px] text-ink-2">
              profit from {profitFrom ?? "—"} hit{profitFrom === 1 ? "" : "s"} ·{" "}
              {pct(strategy.slip.p_profit)} of weeks
            </span>
          )}
        </div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
          The rule: draws at 30% or more, highest first, no team twice, at most
          four. Four play שיטה 2/4. Three play as singles. Two or fewer, the pot
          sits out.{" "}
          {draws.length >= 3 ? (
            <>
              This week&apos;s legs:{" "}
              {draws.map((p, i) => (
                <span key={fixtureKey(p)} className="num">
                  {i > 0 && " · "}
                  {p.home} v {p.away} {pct(p.pick_prob)}
                </span>
              ))}
              . Type Winner&apos;s prices under the Draws board for the verdict;
              the advisor prices at fair and never sets the stake.
            </>
          ) : (
            <>
              The candidates below show what missed the cut and by how much.
              Nothing is booked, and the monkey&apos;s pot stays as it is.
            </>
          )}
        </p>
      </div>

      <Section
        title="The picks"
        lede={
          <>
            {draws.length} draws, {homes.length} home wins, {aways.length} away
            wins — each with the probability it was ranked on, the fair price
            that probability implies, and the full 1 / X / 2 so the call can be
            read in context instead of taken on faith. No team appears twice on
            a board.
          </>
        }
      >
        {/* THE ACCUMULATOR, first, because it is the board the gold pot bets
            since 2026-11-27. Eight seasons walk-forward put the cap at four
            legs: 3.1 of 4 land on average, the whole ticket one week in
            three against 27% stated, and from five legs the return at the
            book goes negative. The one-in-three is written on the board so
            nobody reads a 4-fold as a sure thing. */}
        {w.acca ? (
          <PickGroup
            title={`Best bets · ${w.acca.n}-fold`}
            note={
              w.acca.n === 0
                ? `No call reaches ${pct(w.acca.floor)} this window, so no ticket.`
                : `The strongest ${w.acca.n} calls at or above ${pct(w.acca.floor)}, any side, no team twice, capped at ${w.acca.cap}. ` +
                  `One line: fair price ${w.acca.fair?.toFixed(2)}, lands ${pct(w.acca.p_all ?? 0)} of weeks by the model's own numbers ` +
                  `(historically a third, the strongest calls run ahead of their stated odds); on average ${w.acca.expected_legs} of ${w.acca.n} legs land. ` +
                  (w.acca.booked ? "This is the gold ledger's booked ticket." : "The gold pot books this at one unit a week.")
            }
            picks={w.acca.legs}
            book={{ defaultK: w.acca.n, store: `betting.book.${w.booked ?? w.window?.start}.acca` }}
          />
        ) : null}
        {!w.acca ? (
          <p className="text-[12.5px] text-ink-3">
            Best bets: the API serving this page predates the accumulator
            board; restart main.py.
          </p>
        ) : null}
        <PickGroup
          title="Draws"
          note={`The ticket, and the only board the slip pot bets. Ranked by the published draw probability — the same number the site shows — across the five leagues, normal confidence only; an exact tie goes to the form arm's classifier. Since 27 November a leg under 30% does not make the ticket: four qualifying draws play שיטה 2/4, three play as singles, fewer sit the week out${draws.length < 4 ? ` — ${draws.length} qualify this round` : ""}.`}
          picks={draws}
          book={{ defaultK: 2, store: `betting.book.${w.booked ?? w.window?.start}.draws` }}
        />
        <PickGroup
          title="Home wins"
          note="Ranked on P(home) from the published triplet."
          picks={homes}
          book={{ defaultK: homes.length, store: `betting.book.${w.booked ?? w.window?.start}.home` }}
        />
        <PickGroup
          title="Away wins"
          note="Ranked on P(away). The pool is deliberately wide — a strong away favourite is tier-gold exactly the way a home one is."
          picks={aways}
          book={{ defaultK: aways.length, store: `betting.book.${w.booked ?? w.window?.start}.away` }}
        />
      </Section>

      {candidates.length > draws.length && (
        <Section
          title="The pool the four came from"
          lede="Ranks past the ticket. The first four are committed and ledger-graded; these are here so a better-priced alternate can be swapped in by hand."
        >
          <Candidates rows={candidates.slice(draws.length)} />
        </Section>
      )}

      {strategy && (
        <Section
          title="The advisor's slip"
          lede="The structure the rule picked this week, the legs it is built from, what each hit count returns at fair prices, and the shapes ranked underneath it."
        >
          <WinnerForm s={strategy} />
        </Section>
      )}

      {w.trixy && draws.length > 0 && (
        <Section
          title="How many of the four land"
          lede="The honest frame around everything above it. Four legs at about a third each is a board that resolves harshly — the likeliest single week is one of the four."
        >
          <Trixy trixy={w.trixy} n={draws.length} profitFrom={profitFrom} />
        </Section>
      )}

      {watchlist.length > 0 && (
        <Section
          title="Watchlist"
          lede="Draw numbers that would be ticket-grade if the confidence were there. Shown for judgement, never picked and never committed — the probability rests on league-average priors rather than on these teams."
        >
          <Watchlist rows={watchlist} />
        </Section>
      )}

      <Section
        title="Every fixture in the window"
        lede={
          <>
            The denominator. Picked rows are flagged with their mark and rank;
            everything else is here so &ldquo;why not that one&rdquo; can be
            answered by reading across the row — a lower number, low
            confidence, or a team already on the board.
          </>
        }
      >
        <AllFixtures all={w.all_predictions} marked={marked} />
      </Section>
    </div>
  );
}
