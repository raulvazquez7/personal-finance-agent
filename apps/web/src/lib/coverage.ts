/** Statement coverage for the year board on /imports (spec 2026-10-17, section 5). Pure: dates are
 * YYYY-MM-DD strings compared as text, and a month runs from its first to its last day, in UTC. */

export type Coverage = "covered" | "partial" | "gap" | "outside";
export type Span = { start: string; end: string };
export type AccountRef = { id: string; name: string; digits: string | null };
export type ImportSpan = { accountId: string; start: string | null; end: string | null };
export type CoverageLine = { id: string; name: string; count: number };
export type PartialLine = CoverageLine & { spans: Span[] };
export type MonthDetail = { covered: CoverageLine[]; partial: PartialLine[]; missing: { id: string; name: string }[] };
export type BoardAccount = AccountRef & { states: Coverage[] };
export type YearBoard = { months: string[]; accounts: BoardAccount[]; byMonth: MonthDetail[] };
export type MissingEntry = { month: string; names: string[] };

const DAY_MS = 86_400_000;
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);
const nextDay = (day: string) => iso(Date.parse(`${day}T00:00:00Z`) + DAY_MS);

/** "2026-02" → 1 to 28 February. Day 0 of the next month is this month's last day. */
export function monthSpan(month: string): Span {
  const [year, index] = month.split("-").map(Number);
  return { start: `${month}-01`, end: iso(Date.UTC(year, index, 0)) };
}

const overlaps = (period: Span, month: Span) => period.start <= month.end && period.end >= month.start;
const covers = (period: Span, month: Span) => period.start <= month.start && period.end >= month.end;
const clip = (period: Span, month: Span): Span => ({
  start: period.start > month.start ? period.start : month.start,
  end: period.end < month.end ? period.end : month.end,
});

/** Spans that touch or overlap become one, so 1–5 and 6–8 read as 1–8. */
export function mergeSpans(spans: Span[]): Span[] {
  const merged: Span[] = [];
  for (const span of [...spans].sort((a, b) => a.start.localeCompare(b.start))) {
    const last = merged.at(-1);
    if (last && span.start <= nextDay(last.end)) {
      if (span.end > last.end) last.end = span.end;
    } else {
      merged.push({ ...span });
    }
  }
  return merged;
}

/** The four rules of spec section 5, in order. A month is expected only once it has ended. */
export function monthState(periods: Span[], month: Span, today: string): Coverage {
  if (periods.some((period) => covers(period, month))) return "covered";
  if (periods.some((period) => overlaps(period, month))) return "partial";
  if (month.end < today && periods.some((period) => period.end < month.start)) return "gap";
  return "outside";
}

const periodsOf = (imports: ImportSpan[], accountId: string): Span[] =>
  imports.flatMap((row) => (row.accountId === accountId && row.start && row.end ? [{ start: row.start, end: row.end }] : []));

export function buildYear(accounts: AccountRef[], imports: ImportSpan[], year: number, today: string): YearBoard {
  const months = Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
  const rows = [...accounts]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((account) => {
      const periods = periodsOf(imports, account.id);
      return { account, periods, states: months.map((month) => monthState(periods, monthSpan(month), today)) };
    });
  const byMonth = months.map((month, index): MonthDetail => {
    const span = monthSpan(month);
    const detail: MonthDetail = { covered: [], partial: [], missing: [] };
    for (const { account, periods, states } of rows) {
      const hitting = periods.filter((period) => overlaps(period, span));
      const line = { id: account.id, name: account.name, count: hitting.length };
      if (states[index] === "covered") detail.covered.push(line);
      if (states[index] === "partial") detail.partial.push({ ...line, spans: mergeSpans(hitting.map((p) => clip(p, span))) });
      if (states[index] === "gap") detail.missing.push({ id: account.id, name: account.name });
    }
    return detail;
  });
  return { months, accounts: rows.map(({ account, states }) => ({ ...account, states })), byMonth };
}

/** The board opens on the latest statement's year; the arrows run from the earliest statement's
 * year to the later of that year and today's. */
export function yearBounds(imports: ImportSpan[], today: string): { first: number; last: number; initial: number } {
  const current = Number(today.slice(0, 4));
  const starts = imports.flatMap((row) => (row.start && row.end ? [row.start] : [])).sort();
  const ends = imports.flatMap((row) => (row.start && row.end ? [row.end] : [])).sort();
  if (ends.length === 0) return { first: current, last: current, initial: current };
  const initial = Number(ends[ends.length - 1].slice(0, 4));
  return { first: Number(starts[0].slice(0, 4)), last: Math.max(initial, current), initial };
}

/** The missing line above the board: each month with a gap, newest first. */
export function missingSummary(board: YearBoard): MissingEntry[] {
  return board.months
    .map((month, index) => ({ month, names: board.byMonth[index].missing.map((line) => line.name) }))
    .filter((entry) => entry.names.length > 0)
    .reverse();
}
