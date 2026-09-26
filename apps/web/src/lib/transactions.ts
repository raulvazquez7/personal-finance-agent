/** The explorer's rows: grouped by day (spec 7.3). */

import type { Schemas } from "./api";

type Tx = Schemas["Transaction"];

export type Day = { day: string; net: number; items: Tx[] };

/** Rows arrive newest first (booked_at desc). A day split across two "Load more" pages still gets
 * one header, because the pages are grouped together after they are merged. */
export function groupByDay(items: Tx[]): Day[] {
  const days: Day[] = [];
  for (const tx of items) {
    const last = days.at(-1);
    if (last && last.day === tx.booked_at) {
      last.items.push(tx);
      last.net += Number(tx.amount);
    } else {
      days.push({ day: tx.booked_at, net: Number(tx.amount), items: [tx] });
    }
  }
  return days;
}
