"use client";

import { Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { periodLabel } from "@/lib/format";
import {
  isDay,
  parseFilters,
  periodChanges,
  replaceParams,
  shiftMonth,
  toSearchParams,
  type Filters,
} from "@/lib/params";

type Choice = Omit<Filters, "accounts">;

/** The period filter (spec 2.6): presets as rows, then one month, then a custom range. The
 * default month is the latest one with data, because statements arrive in batches. */
export function PeriodPicker({ latestDay }: { latestDay: string | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const filters = parseFilters(toSearchParams(search));
  const [open, setOpen] = useState(false);
  const latestMonth = latestDay?.slice(0, 7);
  const [month, setMonth] = useState(filters.month ?? latestMonth ?? "");
  const [start, setStart] = useState(filters.start ?? "");
  const [end, setEnd] = useState(filters.end ?? "");
  const presets: { label: string; choice: Choice }[] = [
    { label: "Latest month", choice: { period: "month" } },
    ...(latestMonth ? [{ label: "Previous month", choice: { period: "month" as const, month: shiftMonth(latestMonth, -1) } }] : []),
    { label: "Last 3 months", choice: { period: "last_3_months" } },
    { label: "Year to date", choice: { period: "ytd" } },
    { label: "Last 12 months", choice: { period: "last_12_months" } },
  ];
  const selected = (choice: Choice) => choice.period === filters.period && choice.month === filters.month;

  function go(choice: Choice) {
    setOpen(false);
    router.push(`${pathname}?${replaceParams(search.toString(), periodChanges(choice))}`);
  }

  function openChange(next: boolean) {
    // The URL may have changed since the last open (a choice, back or forward): start from it.
    if (next) {
      setMonth(filters.month ?? latestMonth ?? "");
      setStart(filters.start ?? "");
      setEnd(filters.end ?? "");
    }
    setOpen(next);
  }

  return (
    <Popover open={open} onOpenChange={openChange}>
      <PopoverTrigger render={<Button variant="secondary" size="sm" className="rounded-full" />}>
        <span className="sr-only">Period: </span>
        {periodLabel(filters, latestDay)}
        <ChevronDown data-icon="inline-end" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 gap-1 p-1">
        <div className="flex flex-col">
          {presets.map(({ label, choice }) => (
            <Button
              key={label}
              variant="ghost"
              className="justify-between"
              aria-pressed={selected(choice)}
              onClick={() => go(choice)}
            >
              {label}
              {selected(choice) && <Check data-icon="inline-end" />}
            </Button>
          ))}
        </div>
        <Separator />
        <form
          className="flex flex-col gap-2 p-2"
          onSubmit={(event) => {
            event.preventDefault();
            go({ period: "month", month });
          }}
        >
          <Field>
            <FieldLabel htmlFor="period-month">One month</FieldLabel>
            {/* Firefox and desktop Safari have no month picker: there the field is a text box, and the
                placeholder and pattern give it the format (Chrome ignores both). */}
            <Input
              id="period-month"
              type="month"
              placeholder="YYYY-MM…"
              pattern="[0-9]{4}-[0-9]{2}"
              value={month}
              max={latestMonth}
              onChange={(event) => setMonth(event.target.value)}
            />
          </Field>
          <Button type="submit" size="sm" disabled={!month}>
            Show month
          </Button>
        </form>
        <Separator />
        <form
          className="flex flex-col gap-2 p-2"
          onSubmit={(event) => {
            event.preventDefault();
            go({ period: "custom", start, end });
          }}
        >
          <FieldGroup className="grid grid-cols-2 gap-2">
            <Field>
              <FieldLabel htmlFor="period-start">From</FieldLabel>
              <Input id="period-start" type="date" value={start} max={end || (latestDay ?? undefined)} onChange={(event) => setStart(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel htmlFor="period-end">To</FieldLabel>
              <Input id="period-end" type="date" value={end} min={start || undefined} max={latestDay ?? undefined} onChange={(event) => setEnd(event.target.value)} />
            </Field>
          </FieldGroup>
          <Button type="submit" size="sm" disabled={!isDay(start) || !isDay(end) || start > end}>
            Apply range
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
