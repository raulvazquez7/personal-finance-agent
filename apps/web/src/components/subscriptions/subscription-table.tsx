import Link from "next/link";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dayLong, money } from "@/lib/format";
import { cn } from "@/lib/utils";

import { CadenceSelect } from "./cadence-select";

type Item = Schemas["SubscriptionOut"];
type Props = { items: Item[]; ended?: boolean };

/** Merchant, cadence, latest amount, per month, last charge. From `sm` it is a table with fixed
 * column widths, so the active and ended tables line up. Below `sm` five columns do not fit: each
 * row becomes a block (the merchant with its last charge beside the per-month amount, then the
 * cadence) and the latest amount is left out. Ended rows do not count in the totals, so their per-month is muted. */
export function SubscriptionTable({ items, ended = false }: Props) {
  const perMonth = ended ? "text-muted-foreground" : "font-semibold";
  return (
    <>
      <ul className="flex flex-col divide-y sm:hidden">
        {items.map((item) => (
          <li key={item.merchant_id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 flex-col">
                <MerchantLink item={item} />
                <span className="text-xs text-muted-foreground">Last charge {dayLong(item.last_charge)}</span>
              </div>
              <span className="shrink-0 text-right">
                <span className={perMonth}>{money(item.monthly_equivalent)}</span>
                <span className="text-xs text-muted-foreground"> a month</span>
              </span>
            </div>
            <Cadence item={item} />
          </li>
        ))}
      </ul>
      <div className="hidden sm:block">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Merchant</TableHead>
              <TableHead className="w-56">Cadence</TableHead>
              <TableHead className="w-32 text-right">Latest amount</TableHead>
              <TableHead className="w-28 text-right">Per month</TableHead>
              <TableHead className="w-32 text-right">Last charge</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.merchant_id}>
                <TableCell className="whitespace-normal">
                  <MerchantLink item={item} />
                </TableCell>
                <TableCell>
                  <Cadence item={item} />
                </TableCell>
                <TableCell className="text-right">{money(item.latest_amount)}</TableCell>
                <TableCell className={cn("text-right", perMonth)}>{money(item.monthly_equivalent)}</TableCell>
                <TableCell className="text-right text-muted-foreground">{dayLong(item.last_charge)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

function MerchantLink({ item }: { item: Item }) {
  return (
    <Link href={`/merchants/${item.merchant_id}?period=last_12_months`} className="min-w-0 font-medium break-words hover:underline">
      {item.merchant_name}
    </Link>
  );
}

function Cadence({ item }: { item: Item }) {
  return (
    <CadenceSelect
      merchantId={item.merchant_id}
      merchantName={item.merchant_name}
      cadence={item.cadence}
      source={item.cadence_source}
    />
  );
}
