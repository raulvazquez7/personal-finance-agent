"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";
import { OTHER_COLOR, groupColor } from "@/lib/colors";
import { byLevel1 } from "@/lib/pickers";

const TYPES = [
  { type: "expense", title: "Expenses" },
  { type: "income", title: "Income" },
  { type: "transfer", title: "Transfers" },
] as const;
type TxType = (typeof TYPES)[number]["type"];

type Props = { categories: Schemas["CategoryOut"][]; slots: Record<string, number> };

/** The taxonomy, read-only: one card per group of the chosen type, with the group's colour from
 * the overview (spec section 6.2). Names are shown as stored. */
export function CategoryBrowser({ categories, slots }: Props) {
  const [type, setType] = useState<TxType>("expense");
  const groupsOf = (of: TxType) => byLevel1(categories.filter((category) => category.tx_type === of));
  const groups = groupsOf(type);

  return (
    <section aria-labelledby="categories-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex max-w-xl flex-col gap-1">
          <h2 id="categories-title" className="text-base font-medium">
            Categories
          </h2>
          <p className="text-sm text-muted-foreground">
            A refund takes the category of its purchase. Transfers never count as income or spending.
          </p>
        </div>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-label="Category type"
          value={[type]}
          onValueChange={(value: string[]) => {
            // A pressed item cannot be released: Base UI sends [] for that, which keeps the type.
            const next = TYPES.find((item) => item.type === value[0]);
            if (next) setType(next.type);
          }}
        >
          {TYPES.map((item) => (
            <ToggleGroupItem key={item.type} value={item.type}>
              {item.title}
              <span className="text-muted-foreground"> {groupsOf(item.type).length}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No categories of this type yet.</p>
      ) : (
        // Columns, not a grid: cards of different heights then leave no holes.
        <div className="gap-3 sm:columns-2 lg:columns-3">
          {groups.map((group) => (
            <Card key={group.value} size="sm" className="mb-3 break-inside-avoid">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="size-2 shrink-0 rounded-full"
                    style={{ background: type === "expense" ? groupColor(group.value, slots) : OTHER_COLOR }}
                  />
                  {group.label}
                  <span className="ml-auto text-xs font-normal text-muted-foreground">{group.items.length}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-1">
                  {group.items.map((category) => (
                    <li key={category.slug}>{category.name}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
