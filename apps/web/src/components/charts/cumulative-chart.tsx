"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney, dayAt, dayShort, daysIn, periodNames } from "@/lib/format";

import { LegendButtons, type LegendItem } from "./legend-buttons";
import { dayTooltipLabel, moneyRow } from "./money-tooltip";

/** `title` names the chart for screen readers: Recharts makes it a focusable application. */
type Props = { cumulative: Schemas["Cumulative"]; period: Schemas["PeriodOut"]; title: string };

/** Spent so far, day by day, against the previous period (spec 7.1). The current line stops at
 * the latest imported day; the x axis always spans the whole current period. */
export function CumulativeChart({ cumulative, period, title }: Props) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const names = periodNames(period);
  const config = {
    current: { label: names.current, color: "var(--primary)" },
    previous: { label: names.previous, color: "var(--chart-previous)" },
  } satisfies ChartConfig;
  const length = daysIn(period.start, period.end);
  const data = Array.from({ length }, (_, index) => ({
    day: index + 1,
    current: cumulative.current[index] ? Number(cumulative.current[index].total) : null,
    previous: cumulative.previous?.[index] ? Number(cumulative.previous[index].total) : null,
  }));
  const dayLabel = (day: number) => dayShort(dayAt(period.start, day - 1));
  // Only the series with points: a period without data has an empty current line, which must not
  // be listed or shown alone (an empty chart). A series isolated before it emptied shows all again.
  // One series gets no legend (spec 7.2): the aria-label, the desc and the card title name its line.
  const legend: LegendItem[] = [];
  if (cumulative.current.length > 0) legend.push({ key: "current", label: names.current, color: config.current.color, shape: "line" });
  if (cumulative.previous?.length) legend.push({ key: "previous", label: names.previous, color: config.previous.color, shape: "line" });
  const shown = legend.some((item) => item.key === isolated) ? isolated : null;
  const lines = legend.map((item) => item.label).join(" against ") || "no data";
  return (
    <div className="flex flex-col gap-3">
      {legend.length > 1 && (
        <LegendButtons chart={title} isolated={shown} onIsolate={setIsolated} items={legend} />
      )}
      <ChartContainer config={config} className="aspect-auto h-56 w-full">
        <AreaChart
          accessibilityLayer
          // aria-label, not title: an SVG <title> also shows as the browser's hover tooltip, over ours.
          aria-label={title}
          desc={`A running total per day: ${lines}. The left and right arrow keys move through the days.`}
          data={data}
          margin={{ top: 8, right: 12, left: 0 }}
        >
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="day"
            type="number"
            domain={[1, length]}
            ticks={[1, Math.ceil(length / 2), length]}
            tickFormatter={dayLabel}
            tickLine={false}
            axisLine={false}
            tickMargin={8}
          />
          <YAxis width={48} tickLine={false} axisLine={false} tickFormatter={(tick: number) => compactMoney(tick)} />
          <ChartTooltip
            content={<ChartTooltipContent labelFormatter={dayTooltipLabel(period.start)} formatter={moneyRow(config)} />}
          />
          <Area
            dataKey="previous"
            type="monotone"
            stroke="var(--color-previous)"
            strokeWidth={2}
            fill="transparent"
            dot={false}
            activeDot={false}
            hide={shown === "current"}
          />
          <Area
            dataKey="current"
            type="monotone"
            stroke="var(--color-current)"
            strokeWidth={2}
            fill="var(--color-current)"
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 4 }}
            hide={shown === "previous"}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
