"use client";

/** How wide the screen is, and how to fill it — without three.
 *
 *  Both hooks are deliberately in their own module. The shell that decides
 *  between a flat map and a 3D scene has to render BEFORE three is fetched,
 *  so anything it imports has to be free of it.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** Tailwind's `sm`. The flat-by-default rule is the same line the rest of the
 *  site already breaks at — `RankTable` swaps its fourteen-column table for
 *  cards here — so a reader crossing the breakpoint sees everything change at
 *  once rather than three times on the way down. */
export const SM = 640;

/** IS THIS A SMALL SCREEN? Undefined until it is known.
 *
 *  A statically exported page is prerendered at build time, where there is no
 *  window, so the first client render MUST match the HTML that shipped or
 *  React throws the tree away and rebuilds it. Returning `undefined` on that
 *  first pass — rather than guessing `false` — lets a caller render the same
 *  neutral thing the server did and decide on the second.
 */
export function useNarrow(max = SM - 1): boolean | undefined {
  const [narrow, setNarrow] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) {
      setNarrow(false);
      return;
    }
    const q = window.matchMedia(`(max-width: ${max}px)`);
    const read = () => setNarrow(q.matches);
    read();
    // `addListener` is the iOS < 14 spelling and still the only one there.
    if (q.addEventListener) {
      q.addEventListener("change", read);
      return () => q.removeEventListener("change", read);
    }
    q.addListener(read);
    return () => q.removeListener(read);
  }, [max]);

  return narrow;
}

type FS = {
  /** the element is filling the screen — by the real API or by the fallback */
  on: boolean;
  /** true when the browser gave us the real thing, false when we faked it */
  native: boolean;
  toggle: () => void;
  exit: () => void;
};

/** Safari's prefixed spellings, which iPad Safari still ships and iPhone
 *  Safari still does not implement for arbitrary elements. */
type MaybeFS = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void> | void;
  webkitEnterFullscreen?: () => Promise<void> | void;
};
type MaybeDoc = Document & {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void> | void;
};

/** FULL SCREEN, AND WHAT TO DO WHEN THERE IS NO SUCH THING.
 *
 *  The Fullscreen API is the right answer and iPhone Safari is the reason it
 *  cannot be the only one: on iOS, `requestFullscreen` on a div does not
 *  exist at all, and where a prefixed form does exist it can still reject —
 *  it must be called from a user gesture, and an iframe needs
 *  `allowfullscreen` on it. A button that silently does nothing is worse than
 *  no button, so failure is not a dead end here: the element is pinned over
 *  the viewport with `position: fixed` instead, which is what "full screen"
 *  means to a reader even if it leaves the browser chrome in place.
 *
 *  The fallback is reported as `native: false` so the caller can say so, and
 *  Escape closes it because on iOS there is no browser-provided way out.
 */
export function useFullscreen(ref: React.RefObject<HTMLElement | null>): FS {
  const [on, setOn] = useState(false);
  const [native, setNative] = useState(true);
  /** kept out of state: read inside the escape handler, and a stale closure
   *  there means Escape stops working after the first toggle */
  const fakeRef = useRef(false);

  // The browser can leave fullscreen without us — Escape, the system gesture,
  // a swipe — so the element's state is the browser's to report, not ours to
  // assume. Without this the button says "exit" over a scene that is already
  // back in the page.
  useEffect(() => {
    const sync = () => {
      const d = document as MaybeDoc;
      const el = d.fullscreenElement ?? d.webkitFullscreenElement ?? null;
      if (!fakeRef.current) setOn(!!el && el === ref.current);
    };
    document.addEventListener("fullscreenchange", sync);
    document.addEventListener("webkitfullscreenchange", sync);
    return () => {
      document.removeEventListener("fullscreenchange", sync);
      document.removeEventListener("webkitfullscreenchange", sync);
    };
  }, [ref]);

  const exit = useCallback(() => {
    const d = document as MaybeDoc;
    if (fakeRef.current) {
      fakeRef.current = false;
      setOn(false);
      setNative(true);
      return;
    }
    if (d.fullscreenElement) void d.exitFullscreen?.();
    else if (d.webkitFullscreenElement) void d.webkitExitFullscreen?.();
    setOn(false);
  }, []);

  const enterFake = useCallback(() => {
    fakeRef.current = true;
    setNative(false);
    setOn(true);
  }, []);

  const toggle = useCallback(() => {
    if (on) {
      exit();
      return;
    }
    const el = ref.current as MaybeFS | null;
    if (!el) return;
    const req = el.requestFullscreen ?? el.webkitRequestFullscreen;
    if (!req) {
      enterFake();
      return;
    }
    // A rejected promise is the iOS case and a THROW is the old-Safari one,
    // so both have to land on the fallback or the button does nothing.
    try {
      const r = req.call(el, { navigationUI: "hide" } as FullscreenOptions);
      if (r && typeof (r as Promise<void>).then === "function") {
        (r as Promise<void>).then(
          () => {
            setNative(true);
            setOn(true);
          },
          enterFake,
        );
      } else {
        setNative(true);
        setOn(true);
      }
    } catch {
      enterFake();
    }
  }, [on, ref, exit, enterFake]);

  // Escape is free with the real API and has to be built for the fallback.
  useEffect(() => {
    if (!on) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" && fakeRef.current) exit();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [on, exit]);

  return { on, native, toggle, exit };
}
