"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { monthSpan, type Coverage, type MonthDetail } from "@/lib/coverage";
import { dayRange, monthLabel, monthShort } from "@/lib/format";
import { plural } from "@/lib/labels";
import { cn } from "@/lib/utils";

import { Swatch } from "./swatch";

type Props = { month: string; detail: MonthDetail; today: string; onOpenChange: (open: boolean) => void };

const statements = (count: number) => (count > 1 ? ` · ${plural(count, "statement", "statements")}` : "");

/** A month's column header. It opens, on hover or click, the accounts and their state for that
 * month. Nothing here filters or links (spec section 4.2). */
export function MonthHeader({ month, detail, today, onOpenChange }: Props) {
  const label = monthShort(month);
  if (`${month}-01` > today) return <span className="text-center text-xs text-muted-foreground">{label}</span>;

  const ended = monthSpan(month).end < today;
  const withStatement = detail.covered.length + detail.partial.length;
  const empty = withStatement + detail.missing.length === 0;
  return (
    <Popover onOpenChange={onOpenChange}>
      <PopoverTrigger
        openOnHover
        render={
          <Button
            variant="ghost"
            size="sm"
            className={cn("w-full px-0 text-xs font-medium", !ended && "text-muted-foreground")}
            aria-label={`${monthLabel(month)}. ${withStatement} with a statement, ${detail.missing.length} missing.`}
          />
        }
      >
        {label}
      </PopoverTrigger>
      <PopoverContent side="right" align="start" className="w-72">
        <PopoverHeader>
          <PopoverTitle>{monthLabel(month)}</PopoverTitle>
          {empty && <PopoverDescription>No statement for this month yet.</PopoverDescription>}
        </PopoverHeader>
        {detail.covered.length > 0 && (
          <Group title={`Whole month · ${detail.covered.length}`}>
            {detail.covered.map((line) => (
              <Line key={line.id} state="covered">
                {line.name}
                {statements(line.count)}
              </Line>
            ))}
          </Group>
        )}
        {detail.partial.length > 0 && (
          <Group title={`Part of the month · ${detail.partial.length}`}>
            {detail.partial.map((line) => (
              <Line key={line.id} state="partial" aside={line.spans.map((span) => dayRange(span.start, span.end)).join(", ")}>
                {line.name}
                {statements(line.count)}
              </Line>
            ))}
          </Group>
        )}
        {detail.missing.length > 0 && (
          <Group title={`Missing · ${detail.missing.length}`}>
            {detail.missing.map((line) => (
              <Line key={line.id} state="gap">
                {line.name}
              </Line>
            ))}
          </Group>
        )}
      </PopoverContent>
    </Popover>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-xs text-muted-foreground">{title}</h3>
      <ul className="flex flex-col gap-0.5">{children}</ul>
    </section>
  );
}

function Line({ state, aside, children }: { state: Coverage; aside?: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <Swatch state={state} className="size-2.5 rounded-sm" />
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {aside && <span className="shrink-0 text-xs text-muted-foreground">{aside}</span>}
    </li>
  );
}
