"use client";

import { useState } from "react";

import { CumulativeChart } from "@/components/charts/cumulative-chart";
import { ScopeMonthsChart, type Series } from "@/components/charts/scope-months-chart";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";
import { previousLabel } from "@/lib/format";

type View = "monthly" | "cumulative";

type Props = {
  name: string;
  months: Schemas["ScopeMonth"][];
  series: Series[];
  cumulative: Schemas["Cumulative"];
  period: Schemas["PeriodOut"];
  split: boolean;
  defaultView: View;
};

/** "<Scope> per month" (mockup 03): Total | By category, and Monthly | Cumulative. The title
 * follows the view: the cumulative line is the running total against the previous period. */
export function SpendingCard({ name, months, series, cumulative, period, split, defaultView }: Props) {
  const [view, setView] = useState<View>(defaultView);
  const [stacked, setStacked] = useState(false);
  const title =
    view === "monthly" ? `${name} per month` : `${name} so far${cumulative.previous ? ` ${previousLabel(period, "long")}` : ""}`;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardAction className="flex flex-wrap justify-end gap-2">
          {split && view === "monthly" && (
            <ToggleGroup
              variant="segment"
              size="sm"
              aria-label="Split"
              value={[stacked ? "split" : "total"]}
              onValueChange={(value: string[]) => value[0] && setStacked(value[0] === "split")}
            >
              <ToggleGroupItem value="total">Total</ToggleGroupItem>
              <ToggleGroupItem value="split">By category</ToggleGroupItem>
            </ToggleGroup>
          )}
          <ToggleGroup
            variant="segment"
            size="sm"
            aria-label="View"
            value={[view]}
            onValueChange={(value: string[]) => value[0] && setView(value[0] as View)}
          >
            <ToggleGroupItem value="monthly">Monthly</ToggleGroupItem>
            <ToggleGroupItem value="cumulative">Cumulative</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent>
        {view === "cumulative" ? (
          <CumulativeChart cumulative={cumulative} period={period} />
        ) : (
          <ScopeMonthsChart
            months={months}
            series={split && stacked ? series : []}
            range={[period.start.slice(0, 7), period.end.slice(0, 7)]}
          />
        )}
      </CardContent>
    </Card>
  );
}
