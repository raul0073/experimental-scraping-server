/** The pitch's dimensions and the Opta conversion — WITHOUT three.
 *
 *  These four values are pure arithmetic and always were, but they lived in
 *  `Pitch3D.tsx`, which imports three. Anything that wanted to know how wide
 *  a pitch is — a flat SVG fallback, a camera table, a bit of shot geometry —
 *  therefore dragged 600KB of WebGL in behind it, which is exactly what the
 *  phone build is trying not to do.
 *
 *  `Pitch3D` re-exports all of it, so every existing import path still works
 *  and there is still only ONE place the conversion is written down.
 */
export const PITCH_L = 105; // along the pitch, scene z
export const PITCH_W = 68; // across the pitch, scene x

/** Opta y (0 = the attacking side's RIGHT touchline) -> scene x. */
export const toX = (optaY: number) => (optaY / 100) * PITCH_W - PITCH_W / 2;
/** Opta x (0 = own goal line) -> scene z. */
export const toZ = (optaX: number) => (optaX / 100) * PITCH_L - PITCH_L / 2;
