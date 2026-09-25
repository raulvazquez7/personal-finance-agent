import type { components } from "./api-types";

export type Schemas = components["schemas"];
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiGet<T>(path: string, init: { signal?: AbortSignal } = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store", signal: init.signal });
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export const euro = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
/** With an explicit sign, so money in (+€25.19) never reads as money out (-€25.19). */
export const signedEuro = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  signDisplay: "exceptZero",
});

export async function apiPost(
  path: string,
  body?: unknown,
  init: { keepalive?: boolean } = {},
): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive: init.keepalive,
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}`);
  }
}

/** Pending review items for the navigation badge; null when the API is unreachable or slow. */
export async function reviewCount(): Promise<number | null> {
  try {
    // The root layout awaits this: a hanging API must not hold every page.
    const count = await apiGet<Schemas["ReviewCount"]>("/review/count", {
      signal: AbortSignal.timeout(2000),
    });
    return count.pending;
  } catch {
    return null;
  }
}
