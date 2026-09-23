"use client";

import { useSyncExternalStore } from "react";

/** A remembered per-browser preference — which league, which panel open.
 *
 *  WHY NOT useState + useEffect. The obvious version reads localStorage in an
 *  effect and calls setState, which is wrong twice: it renders once at the
 *  default and again at the stored value (a cascading render React now warns
 *  about), and the alternative — reading it in a lazy initialiser — makes the
 *  prerendered HTML and the client's first render disagree, which is a
 *  hydration mismatch. localStorage is an external store, and this is the
 *  hook for external stores: getServerSnapshot supplies the default that gets
 *  prerendered, getSnapshot supplies the real value once hydrated, and React
 *  reconciles the two itself.
 *
 *  Storage can be absent or throw — private windows, blocked site data — so
 *  every access is guarded and a failure simply means the preference does not
 *  persist. Nothing here is state the page needs to be correct.
 */
const listeners = new Set<() => void>();

/** localStorage only fires "storage" in OTHER tabs, so writes from this one
 *  have to announce themselves or the reading component never re-renders. */
function emit() {
  for (const l of listeners) l();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

export function setStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* nothing to do — the choice just does not survive the visit */
  }
  emit();
}

/** Returns the stored string, or `fallback` when absent, unreadable, or
 *  being prerendered. Safe to compare by value: React's Object.is sees two
 *  equal strings as unchanged, so re-reading on every render is free. */
export function useStored(key: string, fallback: string): string {
  return useSyncExternalStore(
    subscribe,
    () => {
      try {
        return window.localStorage.getItem(key) ?? fallback;
      } catch {
        return fallback;
      }
    },
    () => fallback,
  );
}
