import Link from "next/link";

import { DeltaText } from "@/components/money/delta-text";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { BreakdownItem } from "@/lib/breakdown";
import { money, percent } from "@/lib/format";

type Props = { items: BreakdownItem[]; nameHeader: string; versus: string; showShare?: boolean };

/** Name (with its colour and a hint), share, amount and the change against the previous period.
 * Each name opens the next level (mockup: every click goes one level deeper). A negative amount
 * (refunds only) is shown as it is (spec 2.1). */
export function BreakdownTable({ items, nameHeader, versus, showShare = true }: Props) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">Nothing in this period.</p>;
  const compared = items.some((item) => item.delta.kind !== "hidden");
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>{nameHeader}</TableHead>
          {showShare && <TableHead className="text-right">Share</TableHead>}
          <TableHead className="text-right">Amount</TableHead>
          {compared && <TableHead className="text-right">{versus}</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.key}>
            <TableCell className="max-w-72 whitespace-normal">
              <div className="flex items-center gap-2.5">
                {item.color && (
                  <span
                    aria-hidden
                    data-slot="series-dot"
                    className="size-2.5 shrink-0 rounded-[3px]"
                    style={{ background: item.color }}
                  />
                )}
                <div className="min-w-0">
                  {item.href ? (
                    <Link href={item.href} className="font-medium hover:underline">
                      {item.name}
                    </Link>
                  ) : (
                    <span className="font-medium">{item.name}</span>
                  )}
                  {item.hint && <p className="truncate text-xs text-muted-foreground">{item.hint}</p>}
                </div>
              </div>
            </TableCell>
            {showShare && <TableCell className="text-right text-muted-foreground">{percent(item.share)}</TableCell>}
            <TableCell className="text-right font-semibold">{money(item.amount)}</TableCell>
            {compared && (
              <TableCell className="text-right">
                <DeltaText value={item.delta} />
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
