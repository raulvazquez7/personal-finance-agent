import type { components } from "./api-types";

export type Schemas = components["schemas"];
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export const euro = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
