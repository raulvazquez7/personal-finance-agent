"use client";

import { Pie, PieChart } from "recharts";

import { DeltaText } from "@/components/money/delta-text";
import { NoData } from "@/components/money/no-data";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { Delta } from "@/lib/delta";
import { moneyWhole } from "@/lib/format";

import { moneyRow } from "./money-tooltip";

export type Slice = { name: string; value: number; fill: string };

type Props = { slices: Slice[]; total: string | null; change: Delta; versus: string; title: string };

/** Part-to-whole at a glance, with the total in the centre (mockup 02). Only positive amounts
 * draw a slice (spec 2.1); the table next to it lists every row. A period without data (`total`
 * null) reads "—" with no change, like the Expenses tile (Decision G). The table is also its
 * keyboard and screen-reader twin, so the donut is no Tab stop: Recharts' arrow keys walk an axis,
 * which a pie does not have. */
export function BreakdownDonut({ slices, total, change, versus, title }: Props) {
  return (
    <div className="relative mx-auto size-52">
      <ChartContainer config={{}} className="aspect-square size-full">
        {/* aria-label, not title: an SVG <title> also shows as the browser's hover tooltip, over ours. */}
        <PieChart accessibilityLayer={false} aria-label={title} desc="The table beside it lists the same rows.">
          <ChartTooltip content={<ChartTooltipContent hideLabel formatter={moneyRow({})} />} />
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            innerRadius="72%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            stroke="var(--card)"
            strokeWidth={2}
            isAnimationActive={false}
            rootTabIndex={-1}
          />
        </PieChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-xs text-muted-foreground">Spent</span>
        <span className="text-2xl font-semibold tracking-tight">{total === null ? <NoData /> : moneyWhole(total)}</span>
        {total !== null && (
          // Kept inside the hole: a long "vs …" label wraps onto a second line.
          <span className="max-w-28 text-xs text-balance">
            <DeltaText value={change} /> {change.kind === "change" && <span className="text-muted-foreground">{versus}</span>}
          </span>
        )}
      </div>
    </div>
  );
}
