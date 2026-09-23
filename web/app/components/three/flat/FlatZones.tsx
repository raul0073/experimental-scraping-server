"use client";

import { useEffect, useRef, useState } from "react";

import { PitchZones } from "../../PitchZones";
import { CELLS, cellLabel, type ZoneValues } from "../zones";

/** THE SAME FIFTEEN CELLS, FLAT — and this one really is the existing
 *  component, not a reimplementation of it.
 *
 *  `app/components/PitchZones.tsx` already draws exactly this: the same cell
 *  keys, the same real channel widths, the same green-through-yellow-to-red
 *  ramp, and the number printed on every cell so the colour is a second
 *  reading of something already legible. `ZoneHeat` was built to match it on
 *  purpose — its own comment says so. There is nothing here to invent.
 *
 *  Two things stand between them. `PitchZones` takes a pixel WIDTH, and a
 *  phone has whatever width it has, so this measures the box and hands it
 *  one. And it explains a cell on HOVER, which a phone does not have, so the
 *  tap goes to the caller's selection instead and the caption under the map
 *  says what the cell means — the same place the 3D view says it.
 */
export function FlatZones({
  values,
  lo,
  hi,
  decimals = 0,
  selected,
  onSelect,
  explain,
}: {
  values: ZoneValues;
  lo: number;
  hi: number;
  decimals?: number;
  selected?: string;
  onSelect?: (cell: string) => void;
  /** what a cell's number means, for the pointer tooltip on a laptop */
  explain?: (cell: string, v: number | undefined, where: string) => string;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const [w, setW] = useState(0);

  /** Measured rather than guessed. A ResizeObserver catches the phone being
   *  turned, the scene going full screen and the two-column layout collapsing
   *  — all three of which change this box without changing the route. */
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => setW(el.clientWidth);
    read();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", read);
      return () => window.removeEventListener("resize", read);
    }
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /** The map is 68 by 105, so it is much taller than it is wide, and on a
   *  phone in portrait a full-width one runs off the bottom of the screen.
   *  Height is the binding constraint, not width. */
  const [h, setH] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => setH(el.clientHeight);
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const width = Math.max(
    120,
    Math.floor(Math.min(w || 260, h ? (h * 68) / 105 : Infinity)),
  );

  return (
    <div ref={box} className="flex h-full w-full items-center justify-center">
      {w > 0 && (
        <div
          // The tap layer sits over the SVG rather than inside it, because
          // `PitchZones` owns its own markup and this must not fork it.
          className="relative"
          style={{ width }}
        >
          <PitchZones
            values={values}
            width={width}
            lo={lo}
            hi={hi}
            decimals={decimals}
            explain={explain}
          />
          <div
            className="absolute inset-x-0 top-0 grid"
            style={{
              height: Math.round((width * 105) / 68),
              // THE CHANNELS ARE NOT FIVE EQUAL STRIPS, and the tap targets
              // must not pretend they are. These are the same edges
              // `PitchZones` and `ZoneHeat` both draw — wings 21.1% each,
              // half-spaces 15.7%, centre 26.4% — listed left to right as
              // the reader sees them. Five equal columns would put a finger
              // on the centre and select a half-space.
              gridTemplateColumns: "21.1% 15.7% 26.4% 15.7% 21.1%",
              gridTemplateRows: "repeat(3, 1fr)",
            }}
            aria-hidden={!onSelect}
          >
            {/* Attacking third at the TOP, to match the picture underneath;
                `CELLS` is listed defensive third first, so the rows are
                walked in reverse. Channels are listed right-to-left in Opta
                order and drawn left-to-right, so each row is reversed too. */}
            {[2, 1, 0].flatMap((t) =>
              [4, 3, 2, 1, 0].map((c) => {
                const key = CELLS[t * 5 + c];
                return (
                  <button
                    key={key}
                    type="button"
                    disabled={!onSelect}
                    onClick={() => onSelect?.(selected === key ? "" : key)}
                    aria-label={cellLabel(key)}
                    aria-pressed={selected === key}
                    className="border-2 border-transparent transition-colors disabled:cursor-default"
                    style={
                      selected === key
                        ? { borderColor: "rgba(255,255,255,0.95)" }
                        : undefined
                    }
                  />
                );
              }),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
