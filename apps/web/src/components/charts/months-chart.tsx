"use client";

import { useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney } from "@/lib/format";

import { LegendButtons } from "./legend-buttons";
import { MonthTick, monthBarShape, type MonthRange } from "./month-axis";
import { moneyRow, monthTooltipLabel } from "./money-tooltip";

const config = {
  income: { label: "Income", color: "var(--ramp-1)" },
  expenses: { label: "Expenses", color: "var(--ramp-4)" },
  savings: { label: "Savings", color: "var(--foreground)" },
} satisfies ChartConfig;

const amount = (value: string | null) => (value === null ? null : Number(value));

/** Twelve months of income and expenses as bars and savings as a line, on one € axis (spec 7.2:
 * no dual axes). Months without imported data are dashed boxes, not zeros. */
export function MonthsChart({ months, range }: { months: Schemas["MonthPoint"][]; range: MonthRange }) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const hidden = (key: string) => isolated !== null && isolated !== key;
  const noData = new Set(months.filter((month) => !month.has_data).map((month) => month.month));
  const data = months.map((month) => ({
    month: month.month,
    income: amount(month.income),
    expenses: amount(month.expenses),
    savings: amount(month.savings),
  }));
  const shape = monthBarShape(range);
  return (
    <div className="flex flex-col gap-3">
      <LegendButtons
        isolated={isolated}
        onIsolate={setIsolated}
        items={[
          { key: "income", label: "Income", color: config.income.color },
          { key: "expenses", label: "Expenses", color: config.expenses.color },
          { key: "savings", label: "Savings", color: config.savings.color, shape: "line" },
        ]}
      />
      <ChartContainer config={config} className="aspect-auto h-64 w-full">
        <ComposedChart accessibilityLayer data={data} barGap={2} margin={{ top: 28, right: 8, left: 0 }}>
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
          <Bar dataKey="income" fill="var(--color-income)" radius={[4, 4, 0, 0]} maxBarSize={24} hide={hidden("income")} shape={shape} />
          <Bar dataKey="expenses" fill="var(--color-expenses)" radius={[4, 4, 0, 0]} maxBarSize={24} hide={hidden("expenses")} shape={shape} />
          <Line
            dataKey="savings"
            type="linear"
            stroke="var(--color-savings)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--color-savings)" }}
            connectNulls={false}
            hide={hidden("savings")}
          />
        </ComposedChart>
      </ChartContainer>
    </div>
  );
}
