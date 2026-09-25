import type { ReactNode } from "react";

import type { ChartConfig } from "@/components/ui/chart";
import { dayAt, dayShort, money, monthLabel } from "@/lib/format";

type Item = { color?: string; payload?: unknown };

/** Tooltip rows: a short line key in the series colour, the series name, and the value in euros
 * as the strong element (dataviz: values lead, labels follow). A month without data reads
 * "no data", never €0.00. */
export function moneyRow(config: ChartConfig) {
  return function MoneyRow(value: unknown, name: unknown, item: Item): ReactNode {
    const key = String(name);
    const fill = (item.payload as { fill?: string } | undefined)?.fill;
    return (
      <div className="flex w-full items-center gap-2">
        <span aria-hidden className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: item.color ?? fill }} />
        <span className="text-muted-foreground">{config[key]?.label ?? key}</span>
        <span className="ml-auto pl-3 font-medium text-foreground">
          {value === null || value === undefined ? "no data" : money(Number(value))}
        </span>
      </div>
    );
  };
}

/** The tooltip title of a month column: "August 2026". */
export function monthTooltipLabel(_label: unknown, payload: readonly { payload?: unknown }[]): ReactNode {
  const month = (payload[0]?.payload as { month?: string } | undefined)?.month;
  return month ? monthLabel(month) : null;
}

/** The tooltip title of day N of a period: "15 Aug". */
export function dayTooltipLabel(start: string) {
  return function DayLabel(_label: unknown, payload: readonly { payload?: unknown }[]): ReactNode {
    const day = (payload[0]?.payload as { day?: number } | undefined)?.day;
    return day ? dayShort(dayAt(start, day - 1)) : null;
  };
}
