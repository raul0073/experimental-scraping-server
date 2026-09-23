/** One football pitch, drawn once, used by every map on the site.
 *
 *  ALWAYS VERTICAL, always attacking upwards: own goal at the bottom, the
 *  opponent's at the top. Every analyst draws it this way and anyone reading
 *  one looks for it this way.
 *
 *  Opta's frame is not the image's. x runs 0 at your own goal line to 100 at
 *  theirs, and y runs 0 at the RIGHT touchline to 100 at the LEFT — so the
 *  left wing only lands on the left of the picture after a flip. Skip it and
 *  every map on the site is mirrored, which nobody notices until a winger is
 *  on the wrong flank in all of them.
 *
 *  Units are metres: 68 across by 105 long, with the real markings at their
 *  real sizes. It costs nothing and it means the penalty area on the picture
 *  is the penalty area, so a shot drawn just outside it really was.
 */
export const W = 68;
export const H = 105;

/** Opta y (0 = right touchline) -> image x, left wing on the left. */
export const X = (y: number) => ((100 - y) / 100) * W;
/** Opta x (0 = own goal line) -> image y, attacking upwards. */
export const Y = (x: number) => ((100 - x) / 100) * H;

export const PITCH_GREEN = "#3f8f4f";

/** The markings, in viewBox units. `from` clips the bottom off for maps that
 *  only need the attacking end — the halfway line and everything above it. */
export function PitchLines({
  stroke = "rgba(255,255,255,0.75)",
  width = 0.4,
  from = 0,
}: {
  stroke?: string;
  width?: number;
  /** lowest Opta x drawn, 0 for a full pitch */
  from?: number;
}) {
  const top = Y(100);
  const bottom = Y(from);
  return (
    <g fill="none" stroke={stroke} strokeWidth={width}>
      <rect
        x="0.4"
        y={top + 0.4}
        width={W - 0.8}
        height={bottom - top - (from > 0 ? 0.4 : 0.8)}
      />
      {from < 50 && (
        <>
          <line x1="0.4" y1={H / 2} x2={W - 0.4} y2={H / 2} />
          <circle cx={W / 2} cy={H / 2} r="9.15" />
        </>
      )}
      {from >= 50 && <line x1="0.4" y1={H / 2} x2={W - 0.4} y2={H / 2} />}
      {/* opponent's end — always drawn */}
      <rect x={(W - 40.3) / 2} y="0.4" width="40.3" height="16.1" />
      <rect x={(W - 18.3) / 2} y="0.4" width="18.3" height="5.1" />
      <path d={`M ${W / 2 - 7.3} 16.5 A 9.15 9.15 0 0 0 ${W / 2 + 7.3} 16.5`} />
      <circle cx={W / 2} cy="11" r="0.4" fill={stroke} stroke="none" />
      {/* own end — only when the map reaches that far */}
      {from === 0 && (
        <>
          <rect x={(W - 40.3) / 2} y={H - 16.5} width="40.3" height="16.1" />
          <rect x={(W - 18.3) / 2} y={H - 5.5} width="18.3" height="5.1" />
          <path
            d={`M ${W / 2 - 7.3} ${H - 16.5} A 9.15 9.15 0 0 1 ${W / 2 + 7.3} ${H - 16.5}`}
          />
          <circle cx={W / 2} cy={H - 11} r="0.4" fill={stroke} stroke="none" />
        </>
      )}
    </g>
  );
}
