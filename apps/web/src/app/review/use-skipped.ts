import { useSyncExternalStore } from "react";

/** Review cards skipped in this tab (spec 9), last skipped last, kept in sessionStorage so a reload
 * keeps them and a new tab starts unskipped. */
const KEY = "review-skip:v1";
const EMPTY = "[]";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function read(): string {
  try {
    return sessionStorage.getItem(KEY) ?? EMPTY;
  } catch {
    return EMPTY; // Storage can throw in private browsing: nothing is skipped.
  }
}

export function useSkipped(): [string[], (key: string) => void] {
  // The server snapshot is empty: hydration matches the server HTML, then React reads the tab's skips.
  const raw = useSyncExternalStore(subscribe, read, () => EMPTY);
  const skipped: string[] = JSON.parse(raw);

  function skip(key: string) {
    try {
      sessionStorage.setItem(KEY, JSON.stringify([...skipped.filter((other) => other !== key), key]));
    } catch {
      return; // Not remembered: the card stays where it is.
    }
    listeners.forEach((listener) => listener());
  }

  return [skipped, skip];
}
