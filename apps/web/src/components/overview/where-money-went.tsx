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
    <Card>
      <CardHeader>
        <CardTitle>Where your money went</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
        <CardAction>
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
        <BreakdownDonut slices={slices} total={total} change={change} versus={versus} />
        <BreakdownTable items={items} nameHeader={HEADERS[dimension]} versus={versus} />
      </CardContent>
    </Card>
  );
}
