import Link from "next/link";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dayLong, money } from "@/lib/format";

import { CadenceSelect } from "./cadence-select";

/** Merchant, cadence, latest amount, per month, last charge. Below `sm` the amount column is omitted. */
export function SubscriptionTable({ items }: { items: Schemas["SubscriptionOut"][] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Merchant</TableHead>
          <TableHead>Cadence</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Latest amount</TableHead>
          <TableHead className="text-right">Per month</TableHead>
          <TableHead className="text-right">Last charge</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.merchant_id}>
            <TableCell className="max-w-72 font-medium whitespace-normal wrap-anywhere">
              <Link href={`/merchants/${item.merchant_id}?period=last_12_months`} className="hover:underline">
                {item.merchant_name}
              </Link>
            </TableCell>
            <TableCell>
              <CadenceSelect
                merchantId={item.merchant_id}
                merchantName={item.merchant_name}
                cadence={item.cadence}
                source={item.cadence_source}
              />
            </TableCell>
            <TableCell className="hidden text-right sm:table-cell">{money(item.latest_amount)}</TableCell>
            <TableCell className="text-right font-semibold">{money(item.monthly_equivalent)}</TableCell>
            <TableCell className="text-right text-muted-foreground">{dayLong(item.last_charge)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
