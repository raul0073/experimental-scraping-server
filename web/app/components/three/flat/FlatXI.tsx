"use client";

import { useEffect, useRef, useState } from "react";

import { PassNetwork } from "../../PassNetwork";
import type { Edge, Spot } from "../formation";

/** THE ELEVEN, FLAT — and this one is the team page's own component too.
 *
 *  `app/components/PassNetwork.tsx` already draws average positions with the
 *  passing links between them, on the same `Pitch.tsx` every flat map uses,
 *  with the same receiver-is-inferred caveat printed on it. `Spot` and `Edge`
 *  are the same records under different field names, so this is a rename and
 *  a measurement, not a second network.
 *
 *  WHAT THE FLAT ONE GIVES UP: the player models, the raised territory
 *  surface under a selected man, and the click that raises it. The surface is
 *  genuinely a 3D thing — it is a height field — so on a phone it is the 3D
 *  button, not this view, that answers "where did he actually play".
 *
 *  NOT WIRED IN BY THIS AGENT. `app/versus/SideXI.tsx` belongs to whoever
 *  owns the versus page; passing `flat={<FlatXI spots={squad.spots}
 *  edges={edges} />}` to its `PitchScene` is all it takes, and until then
 *  that scene shows the "show the 3D pitch" card on a phone instead.
 */
export function FlatXI({
  spots,
  edges,
  resolved,
}: {
  spots: Spot[];
  edges: Edge[];
  /** share of completed passes whose receiver could be inferred, 0-1 */
  resolved?: number;
}) {
  const box = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const read = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    read();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", read);
      return () => window.removeEventListener("resize", read);
    }
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /** A pitch is 68 by 105, so inside a box that is wider than it is tall the
   *  HEIGHT is what binds. Sizing on width alone is how a full-length pitch
   *  ends up running off the bottom of a phone. */
  const width = Math.max(
    140,
    Math.floor(Math.min(size.w || 300, size.h ? (size.h * 68) / 105 : 300)),
  );

  return (
    <div ref={box} className="flex h-full w-full items-center justify-center">
      {size.w > 0 && (
        <PassNetwork
          nodes={spots.map((s) => ({
            n: s.name,
            x: s.x,
            y: s.y,
            t: s.passes,
            a: s.apps,
          }))}
          links={edges}
          resolved={resolved}
          width={width}
        />
      )}
    </div>
  );
}
