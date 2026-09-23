"use client";

/** THE READER'S WEIGHTS, KEPT BETWEEN VISITS.
 *
 *  WHY useSyncExternalStore AND NOT useState. The site is a static export:
 *  every page is rendered to HTML at build time, where there is no
 *  localStorage. A `useState(() => localStorage.getItem(...))` initialiser
 *  therefore produces one tree on the server and a different one in the
 *  browser, and React throws a hydration mismatch — or, worse in a table,
 *  silently keeps the server's markup and drops the reader's saved config.
 *
 *  useSyncExternalStore is the API built for exactly this. It takes a THIRD
 *  argument, the server snapshot, which React also uses for the first client
 *  render; only after hydration does it re-read the real store and re-render.
 *  So the first paint always matches the HTML and the saved weights arrive a
 *  frame later, which is correct rather than merely quiet.
 *
 *  The snapshot is the RAW STRING, not a parsed object. getSnapshot is called
 *  on every render check and must return something referentially stable —
 *  JSON.parse would hand back a new object each time and spin React forever.
 *  Parsing happens once, in a memo, downstream.
 */

import { useCallback, useMemo, useSyncExternalStore } from "react";

const KEY = "predictorous.manager-weights.v1";

let listeners: Array<() => void> = [];
let bound = false;
/** null means "not read yet"; "" means "nothing stored". */
let cached: string | null = null;

function emit() {
  for (const l of [...listeners]) l();
}

function onStorage(e: StorageEvent) {
  // e.key is null when the whole store was cleared.
  if (e.key === null || e.key === KEY) {
    cached = null;
    emit();
  }
}

function subscribe(cb: () => void): () => void {
  listeners.push(cb);
  if (!bound) {
    bound = true;
    window.addEventListener("storage", onStorage);
  }
  return () => {
    listeners = listeners.filter((l) => l !== cb);
    if (!listeners.length && bound) {
      bound = false;
      window.removeEventListener("storage", onStorage);
    }
  };
}

function getSnapshot(): string {
  if (cached === null) {
    // Private windows and blocked site data both throw here rather than
    // returning null. A config that cannot be saved is a small loss; a page
    // that will not render is not.
    try {
      cached = window.localStorage.getItem(KEY) ?? "";
    } catch {
      cached = "";
    }
  }
  return cached;
}

/** What the build-time render sees, and what the first client render sees
 *  with it. Nothing stored, so: the defaults. */
function getServerSnapshot(): string {
  return "";
}

export type Stored = Record<string, number> | null;

export function useStoredWeights(): {
  stored: Stored;
  save: (w: Record<string, number>) => void;
  clear: () => void;
} {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const stored = useMemo<Stored>(() => {
    if (!raw) return null;
    try {
      const v: unknown = JSON.parse(raw);
      if (!v || typeof v !== "object" || Array.isArray(v)) return null;
      const out: Record<string, number> = {};
      for (const [k, n] of Object.entries(v as Record<string, unknown>)) {
        if (typeof n === "number" && Number.isFinite(n)) {
          out[k] = Math.max(0, Math.round(n));
        }
      }
      return out;
    } catch {
      // Someone else's key, or a half-written value. Defaults are a better
      // answer than an error boundary.
      return null;
    }
  }, [raw]);

  const write = useCallback((next: string | null) => {
    try {
      if (next === null) window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, next);
    } catch {
      /* storage unavailable: this session still works, it just will not keep */
    }
    cached = next ?? "";
    emit();
  }, []);

  const save = useCallback(
    (w: Record<string, number>) => write(JSON.stringify(w)),
    [write],
  );
  const clear = useCallback(() => write(null), [write]);

  return { stored, save, clear };
}
