/** The import history on /imports, one group per month in which a statement ends (spec section
 * 4.3). The API already sorts by `period_end` (newest first), so a month's rows are adjacent. */

export type HistoryGroup<T> = { month: string | null; rows: T[] };

export function groupByEndMonth<T extends { period_end: string | null }>(rows: T[]): HistoryGroup<T>[] {
  const groups: HistoryGroup<T>[] = [];
  const undated: T[] = [];
  for (const row of rows) {
    if (!row.period_end) {
      undated.push(row);
      continue;
    }
    const month = row.period_end.slice(0, 7);
    const last = groups.at(-1);
    if (last?.month === month) last.rows.push(row);
    else groups.push({ month, rows: [row] });
  }
  return undated.length > 0 ? [...groups, { month: null, rows: undated }] : groups;
}
