import {
  ZONE_ORDER,
  ZONE_STYLE,
  type Zone,
  type ZoneKey,
} from "@/lib/data";

const labelOf = (zones: Zone[], key: ZoneKey) =>
  key === "mid" ? "Mid-table" : (zones.find((z) => z.key === key)?.label ?? key);

/** One club's whole season in a single bar: every simulated finish, grouped
 *  by what that position actually wins or costs in THIS league. */
export function ZoneBar({
  zone,
  zones,
}: {
  zone: Partial<Record<ZoneKey, number>>;
  zones: Zone[];
}) {
  const segments = ZONE_ORDER.filter((k) => (zone[k] ?? 0) > 0.05);
  return (
    <div
      className="flex h-3 w-full min-w-[180px] overflow-hidden rounded-full"
      role="img"
      aria-label={segments
        .map((k) => `${labelOf(zones, k)} ${zone[k]}%`)
        .join(", ")}
    >
      {segments.map((k) => (
        <div
          key={k}
          style={{ width: `${zone[k]}%`, background: ZONE_STYLE[k].fill }}
          title={`${labelOf(zones, k)} — ${zone[k]}%`}
        />
      ))}
    </div>
  );
}

/** The single sentence a reader wants: what is this club actually playing
 *  for? Reported only when one outcome is clearly dominant. */
export function Fighting({
  zone,
  zones,
}: {
  zone: Partial<Record<ZoneKey, number>>;
  zones: Zone[];
}) {
  const europe = (["ucl", "uclq", "uel", "uecl"] as ZoneKey[]).reduce(
    (a, k) => a + (zone[k] ?? 0),
    0,
  );
  const danger = (zone.rel ?? 0) + (zone.playoff ?? 0);

  let key: ZoneKey | "europe" | "safe";
  let value: number;
  if (danger >= 25) {
    key = "rel";
    value = danger;
  } else if ((zone.ucl ?? 0) >= 40) {
    key = "ucl";
    value = zone.ucl ?? 0;
  } else if (europe >= 25) {
    key = "europe";
    value = europe;
  } else if (danger >= 10) {
    key = "playoff";
    value = danger;
  } else {
    key = "safe";
    value = zone.mid ?? 0;
  }

  const style =
    key === "europe" ? ZONE_STYLE.uel : key === "safe" ? ZONE_STYLE.mid : ZONE_STYLE[key];
  const text =
    key === "rel"
      ? "Fighting relegation"
      : key === "playoff"
        ? "Drop-zone risk"
        : key === "ucl"
          ? labelOf(zones, "ucl")
          : key === "europe"
            ? "Chasing Europe"
            : "Mid-table";

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11.5px] font-semibold ${style.chip}`}
      style={{ color: style.text }}
    >
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: style.fill }}
      />
      {text}
      {key !== "safe" ? (
        <span className="num font-normal opacity-80">{Math.round(value)}%</span>
      ) : null}
    </span>
  );
}

export function ZoneLegend({ zones }: { zones: Zone[] }) {
  const keys = ZONE_ORDER.filter(
    (k) => k === "mid" || zones.some((z) => z.key === k),
  );
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11.5px] text-ink-2">
      {keys.map((k) => (
        <span key={k} className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: ZONE_STYLE[k].fill }}
          />
          {labelOf(zones, k)}
        </span>
      ))}
    </div>
  );
}
