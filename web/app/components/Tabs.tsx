"use client";

import { useSyncExternalStore } from "react";

/** The pill row, in one place.
 *
 *  Mental had its own copy and the team page was about to grow a second one.
 *  Two copies of a control is how a site ends up with pills that are nearly
 *  the same size in nearly the same blue.
 *
 *  Which tab is open lives in the URL, so a page can be linked to the part
 *  of it worth reading and the browser's back button steps through the tabs
 *  rather than leaving the page. Written with replaceState: a Next
 *  navigation would remount the page and throw away the payload it has
 *  already fetched, and a static export has no server to ask anyway.
 *
 *  THE URL IS THE STORE, not a copy of it in state. The prerendered HTML has
 *  no URL to read, so the server snapshot is the first tab and the client
 *  snapshot is whatever the query string says; React reconciles the two
 *  without a hydration mismatch and without the read-then-setState effect
 *  this used to be. replaceState fires no event, so a write from this tab
 *  announces itself; popstate covers the back button.
 */
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("popstate", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("popstate", cb);
  };
}

export function useTab<T extends string>(key: string, tabs: readonly T[]): [T, (t: T) => void] {
  const tab = useSyncExternalStore(
    subscribe,
    () => {
      const got = new URLSearchParams(window.location.search).get(key);
      return got && (tabs as readonly string[]).includes(got) ? (got as T) : tabs[0];
    },
    () => tabs[0],
  );
  const pick = (t: T) => {
    const u = new URL(window.location.href);
    if (t === tabs[0]) u.searchParams.delete(key);
    else u.searchParams.set(key, t);
    window.history.replaceState(null, "", u);
    for (const l of listeners) l();
  };
  return [tab, pick];
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  labels,
}: {
  tabs: readonly T[];
  value: T;
  onChange: (t: T) => void;
  /** what each tab is called, if not the key itself */
  labels?: Partial<Record<T, string>>;
}) {
  return (
    <div role="tablist" className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t}
          role="tab"
          aria-selected={value === t}
          onClick={() => onChange(t)}
          className={`rounded-full border px-4 py-1 text-[13px] font-medium capitalize transition-colors ${
            value === t
              ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
              : "border-line bg-card text-ink-2 hover:border-ink-3"
          }`}
        >
          {labels?.[t] ?? t}
        </button>
      ))}
    </div>
  );
}
