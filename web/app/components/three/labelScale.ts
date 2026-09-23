"use client";

import { createContext, useContext } from "react";

/** HOW BIG AN IN-SCENE LABEL SHOULD BE ON *THIS* CANVAS.
 *
 *  `<Html distanceFactor={n}>` renders at roughly `n / distance` CSS pixels
 *  per world unit. That is a size in PIXELS, and it does not know how many
 *  pixels the canvas has. So every label on this site is tuned against a
 *  laptop-width canvas, and the same number on a phone draws the same
 *  physical label over a pitch a third of the width — a player's name across
 *  half the goal, four zone figures overlapping into a smear. It reads as the
 *  scene being broken rather than as a label being mis-tuned, which is how
 *  this class of bug survives.
 *
 *  The fix is a ratio, applied once: `distanceFactor={26 * scale}`. Provided
 *  from inside the canvas, where the real size is known, and consumed through
 *  context rather than by having each of four hundred shot labels subscribe
 *  to the renderer's size itself.
 *
 *  Not linear. At half the width a label should not be half the size — it
 *  should be somewhat smaller, or the text on a phone becomes unreadable,
 *  which is a different way of failing. The square root splits the
 *  difference, and the floor stops a very narrow canvas from producing type
 *  nobody can read at all.
 */
export const LABEL_REF = 900; // the canvas width every distanceFactor was tuned on

export const labelScaleFor = (width: number) =>
  Math.min(1, Math.max(0.55, Math.sqrt(Math.max(width, 1) / LABEL_REF)));

export const LabelScale = createContext(1);

export const useLabelScale = () => useContext(LabelScale);
