"use client";

import { useState } from "react";

import { BreakdownTable } from "@/components/breakdown/breakdown-table";
import { BreakdownDonut } from "@/components/charts/breakdown-donut";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { BreakdownItem } from "@/lib/breakdown";
import { OTHER_COLOR } from "@/lib/colors";
import type { Delta } from "@/lib/delta";
import type { Dimension } from "@/lib/labels";

const HEADERS: Record<Dimension, string> = { group: "Group", category: "Category", merchant: "Merchant" };

type Props = { views: Record<Dimension, BreakdownItem[]>; total: string | null; change: Delta; versus: string; subtitle: string };

/** "Where your money went" (spec 7.1): donut + table, Groups by default. The Groups view gives
 * every group with spend its own row and slice, grey without a colour slot; the Categories and
 * Merchants views paint each slice and row with its group's colour (spec 7.2). */
export function WhereMoneyWent({ views, total, change, versus, subtitle }: Props) {
  const [dimension, setDimension] = useState<Dimension>("group");
  const items = views[dimension];
  const slices = items
    .filter((item) => Number(item.amount) > 0)
    .map((item) => ({ name: item.name, value: Number(item.amount), fill: item.color ?? OTHER_COLOR }));
  return (
    // overflow-clip, not the card's overflow-hidden: a hidden overflow makes the card a scroll
    // container, and the sticky donut below would stick to the card instead of the page.
    <Card className="overflow-clip">
      {/* Below sm the switch goes under the title: beside it, the title wrapped to four lines. */}
      <CardHeader className="max-sm:has-data-[slot=card-action]:grid-cols-1">
        <CardTitle>Where your money went</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
        <CardAction className="max-sm:col-start-1 max-sm:row-span-1 max-sm:row-start-auto max-sm:justify-self-start">
          <ToggleGroup
            variant="segment"
            size="sm"
            aria-label="Break down by"
            value={[dimension]}
            onValueChange={(value: string[]) => value[0] && setDimension(value[0] as Dimension)}
          >
            <ToggleGroupItem value="group">Groups</ToggleGroupItem>
            <ToggleGroupItem value="category">Categories</ToggleGroupItem>
            <ToggleGroupItem value="merchant">Merchants</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent className="grid items-center gap-6 md:grid-cols-[13rem_minmax(0,1fr)]">
        {/* From md the donut sits at the top and follows the scroll: centred beside an opened
            "Other" of a hundred rows, it would sit thousands of pixels down the page. */}
        <div className="md:sticky md:top-6 md:self-start">
          <BreakdownDonut
            slices={slices}
            total={total}
            change={change}
            versus={versus}
            title={`Spending by ${HEADERS[dimension].toLowerCase()}`}
          />
        </div>
        <BreakdownTable items={items} nameHeader={HEADERS[dimension]} versus={versus} />
      </CardContent>
    </Card>
  );
}
