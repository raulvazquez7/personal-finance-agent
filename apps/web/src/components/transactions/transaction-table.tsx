import { Fragment } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dayHeader, signedMoney } from "@/lib/format";
import { groupByDay } from "@/lib/transactions";

import { TransactionRow } from "./transaction-row";

type Tx = Schemas["Transaction"];

type Props = { items: Tx[]; onOpen?: (tx: Tx) => void; showSource?: boolean };

/** Rows grouped by day; each day header shows that day's net (spec 7.3). */
export function TransactionTable({ items, onOpen, showSource = false }: Props) {
  const columns = showSource ? 5 : 4;
  return (
    <Table>
      <TableHeader className="sr-only">
        <TableRow>
          <TableHead>Merchant</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Account</TableHead>
          {showSource && <TableHead>Categorized by</TableHead>}
          <TableHead>Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {groupByDay(items).map((day) => (
          <Fragment key={day.day}>
            <TableRow data-day={day.day} className="hover:bg-transparent">
              <TableCell colSpan={columns} className="pt-4 pb-1 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <span>{dayHeader(day.day)}</span>
                  <span>{signedMoney(day.net)}</span>
                </div>
              </TableCell>
            </TableRow>
            {day.items.map((tx) => (
              <TransactionRow key={tx.id} tx={tx} showSource={showSource} onOpen={onOpen && (() => onOpen(tx))} />
            ))}
          </Fragment>
        ))}
      </TableBody>
    </Table>
  );
}
