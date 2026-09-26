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

/** What the top bar's filters need: the accounts, and the latest imported day, which is the
 * default month (spec 2.6). Empty when the API is unreachable or slow, like reviewCount. */
export async function filterContext(): Promise<{ accounts: Schemas["Account"][]; latestDay: string | null }> {
  try {
    const signal = AbortSignal.timeout(2000);
    const [accounts, page] = await Promise.all([
      apiGet<Schemas["Account"][]>("/accounts", { signal }),
      // No endpoint returns the latest day alone; every period read carries it in `period`.
      apiGet<Schemas["TransactionPage"]>("/transactions?limit=1", { signal }),
    ]);
    return { accounts, latestDay: page.period.latest_day };
  } catch {
    return { accounts: [], latestDay: null };
  }
}
