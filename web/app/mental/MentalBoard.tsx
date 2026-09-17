"use client";

import { useEffect, useMemo, useState } from "react";

type Metric = {
  key: string;
  label: string;
  unit: string;
  group: string;
  invert: boolean;
  desc: string;
};
type Player = {
  n: string;
  t: string;
  p: string;
  m: number;
  v: Record<string, number>;
  q: Record<string, number>;
};
type Data = {
  league: string;
  seasons: string[];
  min_minutes: number;
  groups: { key: string; label: string }[];
  metric_groups: { key: string; label: string }[];
  metrics: Metric[];
  reliability: Record<string, Record<string, number>>;
  players: Record<string, Player[]>;
};

/** Starting points only — every weight is yours to change. Nothing here is
 *  a claim about what "mental" means; that is the question the page exists
 *  to let you answer. */
const PRESETS: Record<string, Record<string, number>> = {
  CB: { aerial_def_pct: 20, duel_90: 15, interception_90: 15, tackle_pct: 12,
        recovery_90: 12, pass_pct: 10, clearance_90: 8, foul_90: 8 },
  FB: { duel_90: 15, tackle_pct: 12, interception_90: 12, recovery_90: 12,
        cross_90: 12, takeon_90: 12, prog_pass_90: 10, pass_pct: 10,
        aerial_def_pct: 5 },
  CM: { prog_pass_90: 18, pass_pct: 15, recovery_90: 15, duel_90: 15,
        interception_90: 10, final_third_90: 10, tackle_pct: 10, pass_90: 7 },
  AM: { keypass_90: 20, takeon_90: 15, box_pass_90: 15, throughball_90: 10,
        prog_pass_90: 10, duel_90: 10, pass_pct: 10, dispossessed_90: 10 },
  WIDE: { takeon_90: 20, keypass_90: 15, box_pass_90: 10, cross_pct: 10,
          touch_box_90: 10, carry_box_90: 10, duel_90: 10,
          dispossessed_90: 8, pass_pct: 7 },
  ST: { touch_box_90: 20, aerial_att_pct: 15, duel_90: 15, bigchance_90: 10,
        keypass_90: 10, takeon_90: 10, dispossessed_90: 10, pass_pct: 10 },
  GK: { pass_pct: 60, pass_90: 40 },
};

const RELIABLE = 0.6;
const MARGINAL = 0.4;

function relTone(rho?: number) {
  if (rho === undefined) return { cls: "text-ink-3", tip: "not tested for this position yet" };
  if (rho >= RELIABLE) return { cls: "text-good", tip: `repeats across seasons (${rho})` };
  if (rho >= MARGINAL) return { cls: "text-[#9a7400]", tip: `marginal (${rho})` };
  return { cls: "text-bad", tip: `does NOT repeat (${rho}) — a rating built on this is decoration` };
}

export function MentalBoard() {
  const [data, setData] = useState<Data | null>(null);
  const [season, setSeason] = useState<string>("");
  const [pos, setPos] = useState("WIDE");
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [blockUnreliable, setBlockUnreliable] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [minMinutes, setMinMinutes] = useState(900);

  useEffect(() => {
    fetch("/data/mental.json")
      .then((r) => r.json())
      .then((d: Data) => {
        setData(d);
        setSeason(d.seasons[d.seasons.length - 1]);
        setWeights(PRESETS.WIDE);
      })
      .catch(() => setData(null));
  }, []);

  const rel = (key: string) => data?.reliability?.[key]?.[pos];

  const rows = useMemo(() => {
    if (!data || !season) return [];
    const active = Object.entries(weights).filter(([k, w]) => {
      if (w <= 0) return false;
      if (blockUnreliable) {
        const r = rel(k);
        if (r !== undefined && r < MARGINAL) return false;
      }
      return true;
    });
    const total = active.reduce((a, [, w]) => a + w, 0) || 1;
    return (data.players[season] ?? [])
      .filter((p) => p.p === pos && p.m >= minMinutes)
      .map((p) => {
        let score = 0;
        for (const [k, w] of active) score += (p.q[k] ?? 50) * w;
        return { ...p, score: score / total };
      })
      .sort((a, b) => b.score - a.score);
  }, [data, season, pos, weights, blockUnreliable, minMinutes]);

  if (!data) {
    return <p className="text-[13.5px] text-ink-2">Loading the board…</p>;
  }

  const shown = data.metrics.filter(
    (m) => showAll || (weights[m.key] ?? 0) > 0,
  );
  const cols = Object.entries(weights)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([k]) => k);
  const byKey = Object.fromEntries(data.metrics.map((m) => [m.key, m]));

  return (
    <div>
      {/* ---------------------------------------------------- controls */}
      <div className="flex flex-wrap items-center gap-2">
        {data.groups.map((g) => (
          <button
            key={g.key}
            onClick={() => {
              setPos(g.key);
              setWeights(PRESETS[g.key] ?? {});
            }}
            className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium transition-colors ${
              pos === g.key
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {g.label}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-2 text-[12.5px] text-ink-2">
          min minutes
          <select
            value={minMinutes}
            onChange={(e) => setMinMinutes(Number(e.target.value))}
            className="rounded-md border border-line bg-card px-2 py-1"
            title="a bigger sample is a more trustworthy rating, but fewer players qualify"
          >
            {[900, 1200, 1800, 2400, 3000].map((v) => (
              <option key={v} value={v}>
                {v.toLocaleString()}+
              </option>
            ))}
          </select>
        </span>
        <span className="flex items-center gap-2 text-[12.5px] text-ink-2">
          season
          <select
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            className="rounded-md border border-line bg-card px-2 py-1"
          >
            {data.seasons.map((s) => (
              <option key={s} value={s}>
                {s.slice(0, 2)}/{s.slice(2)}
              </option>
            ))}
          </select>
        </span>
        <span className="num text-[12px] text-ink-3">{rows.length} players</span>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[300px_1fr]">
        {/* ------------------------------------------------ the config */}
        <div className="rounded-xl border border-line bg-card p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-semibold">What counts as mental</h2>
            <button
              onClick={() => setShowAll((s) => !s)}
              className="text-[12px] text-home hover:underline"
            >
              {showAll ? "only used" : `all ${data.metrics.length}`}
            </button>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-2">
            Set the weights. The ranking recomputes as you drag. Colour shows
            whether a metric <em>repeats</em> for this position — red ones
            cannot reproduce themselves season to season.
          </p>
          <label className="mt-3 flex items-center gap-2 text-[12px] text-ink-2">
            <input
              type="checkbox"
              checked={blockUnreliable}
              onChange={(e) => setBlockUnreliable(e.target.checked)}
            />
            ignore metrics that don&apos;t repeat
          </label>

          <div className="mt-3 max-h-[640px] space-y-4 overflow-y-auto pr-1">
            {data.metric_groups.map((mg) => {
              const items = shown.filter((m) => m.group === mg.key);
              if (!items.length) return null;
              return (
                <div key={mg.key}>
                  <div className="text-[10.5px] font-semibold uppercase tracking-wider text-ink-3">
                    {mg.label}
                  </div>
                  {items.map((m) => {
                    const r = rel(m.key);
                    const tone = relTone(r);
                    const w = weights[m.key] ?? 0;
                    return (
                      <div key={m.key} className="mt-2">
                        <div className="flex items-baseline justify-between gap-2">
                          <span
                            className={`text-[12.5px] ${tone.cls}`}
                            title={`${m.desc}\n\n${tone.tip}`}
                          >
                            {m.label}
                            {m.invert ? " ↓" : ""}
                          </span>
                          <span className="num text-[11.5px] text-ink-3">
                            {w}
                          </span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={30}
                          value={w}
                          onChange={(e) =>
                            setWeights((prev) => ({
                              ...prev,
                              [m.key]: Number(e.target.value),
                            }))
                          }
                          className="w-full accent-[#4a7ba6]"
                        />
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>

        {/* ------------------------------------------------- the board */}
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                <th className="py-2 pl-4 pr-2 text-left font-semibold">#</th>
                <th className="py-2 pr-3 text-left font-semibold">Player</th>
                <th className="py-2 pr-3 text-left font-semibold">Team</th>
                <th className="px-3 py-2 text-right font-semibold">Score</th>
                {cols.map((c) => (
                  <th
                    key={c}
                    className="px-2 py-2 text-right font-semibold"
                    title={byKey[c]?.desc}
                  >
                    {byKey[c]?.label}
                  </th>
                ))}
                <th className="py-2 pl-2 pr-4 text-right font-semibold">Min</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 60).map((p, i) => (
                <tr key={p.n} className="border-t border-line">
                  <td className="num py-2 pl-4 pr-2 text-ink-3">{i + 1}</td>
                  <td className="whitespace-nowrap py-2 pr-3 font-medium">
                    {p.n}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-[12.5px] text-ink-2">
                    {p.t}
                  </td>
                  <td className="num px-3 py-2 text-right font-semibold">
                    {p.score.toFixed(1)}
                  </td>
                  {cols.map((c) => (
                    <td key={c} className="num px-2 py-2 text-right">
                      {p.v[c] === undefined ? (
                        <span className="text-ink-3">—</span>
                      ) : (
                        <>
                          {p.v[c]}
                          <span className="ml-1 text-[11px] text-ink-3">
                            ({p.q[c] ?? "-"})
                          </span>
                        </>
                      )}
                    </td>
                  ))}
                  <td className="num py-2 pl-2 pr-4 text-right text-[12px] text-ink-3">
                    {p.m}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <p className="p-4 text-[13px] text-ink-2">
              No players — give at least one metric a weight.
            </p>
          )}
        </div>
      </div>

      <p className="mt-3 text-[12px] text-ink-3">
        Numbers are the raw per-90 or percentage, with the player&apos;s
        percentile within his own position in brackets. {data.min_minutes}+
        minutes required. Data: {data.league}, Opta event streams.
      </p>
    </div>
  );
}
