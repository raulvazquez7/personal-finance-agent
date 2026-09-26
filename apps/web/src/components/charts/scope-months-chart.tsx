"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney } from "@/lib/format";

import { LegendButtons } from "./legend-buttons";
import { MonthTick, monthBarShape, type MonthRange } from "./month-axis";
import { moneyRow, monthTooltipLabel } from "./money-tooltip";

/** One stacked series: a child of the scope (a category, or "_other"), in a ramp shade. */
export type Series = { key: string; label: string; color: string };

/** `title` names the chart for screen readers: Recharts makes it a focusable application. */
type Props = { months: Schemas["ScopeMonth"][]; series: Series[]; range: MonthRange; title: string };

/** A scope's 12 months (spec 7.1): one bar per month, or each month stacked by child in the
 * one-hue ramp (spec 7.2). Series keys are s0..s5 because child keys (slugs, "category:…") are not
 * valid CSS variable names. Refund-only months stack below zero (`stackOffset="sign"`). */
export function ScopeMonthsChart({ months, series, range, title }: Props) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const keys = series.map((_, index) => `s${index}`);
  const visible = keys.filter((key) => isolated === null || key === isolated);
  const noData = new Set(months.filter((month) => !month.has_data).map((month) => month.month));
  const data = months.map((month) => ({
    month: month.month,
    total: month.has_data ? Number(month.total) : null,
    ...Object.fromEntries(series.map((s, index) => [`s${index}`, month.has_data ? Number(month.by_child[s.key] ?? 0) : null])),
  }));
  const config: ChartConfig = series.length
    ? Object.fromEntries(series.map((s, index) => [`s${index}`, { label: s.label, color: s.color }]))
    : { total: { label: "Total", color: "var(--primary)" } };
  const shape = monthBarShape(range);
  return (
    <div className="flex flex-col gap-3">
      {series.length > 1 && (
        <LegendButtons
          chart={title}
          isolated={isolated}
          onIsolate={setIsolated}
          items={series.map((s, index) => ({ key: `s${index}`, label: s.label, color: s.color }))}
        />
      )}
      <ChartContainer config={config} className="aspect-auto h-60 w-full">
        <BarChart
          accessibilityLayer
          title={title}
          desc={`One bar per month${series.length > 0 ? ", split by category" : ""}; months without imported data are marked. The left and right arrow keys move through the months.`}
          data={data}
          stackOffset="sign"
          margin={{ top: 28, right: 8, left: 0 }}
        >
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="month"
            interval={0}
            tickLine={false}
            axisLine={false}
            tickMargin={6}
            height={28}
            tick={<MonthTick range={range} noData={noData} />}
          />
          <YAxis width={48} tickLine={false} axisLine={false} tickFormatter={(tick: number) => compactMoney(tick)} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={monthTooltipLabel} formatter={moneyRow(config)} />} />
          {series.length === 0 ? (
            <Bar dataKey="total" fill="var(--color-total)" radius={[4, 4, 0, 0]} maxBarSize={32} shape={shape} />
          ) : (
            keys.map((key) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="months"
                fill={`var(--color-${key})`}
                stroke="var(--card)"
                strokeWidth={1}
                maxBarSize={32}
                radius={key === visible.at(-1) ? [4, 4, 0, 0] : 0}
                hide={!visible.includes(key)}
                shape={shape}
              />
            ))
          )}
        </BarChart>
      </ChartContainer>
    </div>
  );
}
