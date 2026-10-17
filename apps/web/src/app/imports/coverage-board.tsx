"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buildYear, missingSummary, yearBounds, type AccountRef, type Coverage, type ImportSpan } from "@/lib/coverage";
import { monthName } from "@/lib/format";
import { cn } from "@/lib/utils";

import { MonthHeader } from "./month-header";
import { Swatch } from "./swatch";

const LEGEND: { state: Coverage; label: string }[] = [
  { state: "covered", label: "Whole month" },
  { state: "partial", label: "Part of the month" },
  { state: "gap", label: "Missing" },
  { state: "outside", label: "Not expected" },
];

type Props = { accounts: AccountRef[]; imports: ImportSpan[]; today: string };

/** Which months have a statement, for each account, one year at a time (spec section 4.2). */
export function CoverageBoard({ accounts, imports, today }: Props) {
  const bounds = yearBounds(imports, today);
  const [year, setYear] = useState(bounds.initial);
  const [openMonth, setOpenMonth] = useState<string | null>(null);
  const board = buildYear(accounts, imports, year, today);
  const missing = missingSummary(board);

  function go(next: number) {
    setOpenMonth(null);
    setYear(next);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Statement coverage</CardTitle>
        <CardDescription>Which months have a statement, for each account.</CardDescription>
        <CardAction className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            aria-label="Previous year"
            disabled={year <= bounds.first}
            onClick={() => go(year - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="w-12 text-center text-sm font-medium tabular-nums">{year}</span>
          <Button
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            aria-label="Next year"
            disabled={year >= bounds.last}
            onClick={() => go(year + 1)}
          >
            <ChevronRight />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {missing.length === 0 ? (
            <span className="text-muted-foreground">{`Nothing missing in ${year}.`}</span>
          ) : (
            <>
              <Swatch state="gap" className="size-3 rounded-sm" />
              <span className="font-medium">Missing:</span>
              <span>
                {missing
                  .map(({ month, names }) => `${monthName(month)} · ${names.length === 1 ? names[0] : `${names.length} accounts`}`)
                  .join(", ")}
              </span>
            </>
          )}
        </p>
        {/* Thirteen columns: the account, then January to December. On a phone the grid scrolls inside the card. */}
        <div className="overflow-x-auto">
          <div className="grid min-w-[44rem] grid-cols-[minmax(9rem,1.3fr)_repeat(12,minmax(0,1fr))] items-center gap-x-1 gap-y-2">
            {/* A real cell: sr-only is position:absolute, which takes it out of the grid and moves every square one month right. */}
            <span className="text-xs text-muted-foreground">Account</span>
            {board.months.map((month, index) => (
              <MonthHeader
                key={month}
                month={month}
                detail={board.byMonth[index]}
                today={today}
                onOpenChange={(open) => setOpenMonth((current) => (open ? month : current === month ? null : current))}
              />
            ))}
            {board.accounts.map((account) => (
              <div key={account.id} className="col-span-full grid grid-cols-subgrid items-center">
                <span className="truncate pr-2 text-sm" title={account.name}>
                  {account.name}
                  {account.digits && <span className="text-muted-foreground"> {account.digits}</span>}
                </span>
                {account.states.map((state, index) => (
                  <span
                    key={board.months[index]}
                    className={cn(
                      "flex justify-center rounded-md py-0.5",
                      openMonth === board.months[index] && "bg-primary/5",
                    )}
                  >
                    <Swatch state={state} />
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
          {LEGEND.map(({ state, label }) => (
            <li key={state} className="flex items-center gap-1.5">
              <Swatch state={state} className={cn("size-3 rounded-sm", state === "outside" && "border border-input")} />
              {label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
