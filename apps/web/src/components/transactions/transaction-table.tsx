import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dayHeader, signedMoney } from "@/lib/format";
import { groupByDay } from "@/lib/transactions";

import { TransactionRow } from "./transaction-row";

type Tx = Schemas["Transaction"];

type Props = { items: Tx[]; onOpen?: (tx: Tx) => void; showSource?: boolean };

/** Rows grouped by day; each day header shows that day's net (spec 7.3). The screen-reader
 * headers hide with their columns on small screens, and each day is a row group whose header
 * cell names the day for the rows under it. */
export function TransactionTable({ items, onOpen, showSource = false }: Props) {
  const columns = showSource ? 5 : 4;
  return (
    <Table>
      <TableHeader className="sr-only">
        <TableRow>
          <TableHead>Merchant</TableHead>
          <TableHead className="hidden sm:table-cell">Category</TableHead>
          <TableHead className="hidden md:table-cell">Account</TableHead>
          {showSource && <TableHead className="hidden lg:table-cell">Categorized by</TableHead>}
          <TableHead>Amount</TableHead>
        </TableRow>
      </TableHeader>
      {groupByDay(items).map((day) => (
        // The body border stands in for its last row's, which TableBody drops.
        <TableBody key={day.day} className="border-b last:border-0">
          <TableRow data-day={day.day} className="hover:bg-transparent">
            <th
              scope="rowgroup"
              colSpan={columns}
              className="p-2 pt-4 pb-1 text-left align-middle text-xs font-normal whitespace-nowrap text-muted-foreground"
            >
              <div className="flex justify-between">
                <span>{dayHeader(day.day)}</span>
                <span>{signedMoney(day.net)}</span>
              </div>
            </th>
          </TableRow>
          {day.items.map((tx) => (
            <TransactionRow key={tx.id} tx={tx} showSource={showSource} onOpen={onOpen && (() => onOpen(tx))} />
          ))}
        </TableBody>
      ))}
    </Table>
  );
}
