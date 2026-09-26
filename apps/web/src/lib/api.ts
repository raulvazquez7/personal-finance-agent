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

/** A failed write: the HTTP status, and FastAPI's `detail` when it is a sentence (for example
 * the 422 for an income category on money going out). */
export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, detail: string | null, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function send<T>(method: "POST" | "PATCH" | "DELETE", path: string, body?: unknown, keepalive?: boolean): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive,
  });
  if (!response.ok) {
    const detail = await response.json().then(
      (json: { detail?: unknown }) => (typeof json.detail === "string" ? json.detail : null),
      () => null,
    );
    throw new ApiError(response.status, detail, `${method} ${path} failed with ${response.status}`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const apiPost = (path: string, body?: unknown, init: { keepalive?: boolean } = {}) =>
  send<void>("POST", path, body, init.keepalive);
export const apiPatch = <T = void>(path: string, body: unknown) => send<T>("PATCH", path, body);
export const apiDelete = (path: string) => send<void>("DELETE", path);

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
