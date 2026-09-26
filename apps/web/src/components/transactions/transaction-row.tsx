import { Repeat, StickyNote } from "lucide-react";

import { TableCell, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { signedMoney } from "@/lib/format";
import { label, sourceLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

type Tx = Schemas["Transaction"];

// A small dot beside the source's name (spec 7.3); the text carries the meaning.
const SOURCE_DOT: Record<string, string> = {
  rule: "bg-muted-foreground",
  merchant: "bg-ramp-3",
  jev: "bg-primary",
  user: "bg-foreground",
  none: "bg-chart-other",
};

type Props = { tx: Tx; onOpen?: () => void; showSource?: boolean };

/** One transaction (mockup 03): the merchant with the note as a muted second line, group ·
 * category, account, amount, a subscription mark and, in the explorer, who categorized it. */
export function TransactionRow({ tx, onOpen, showSource = false }: Props) {
  const name = tx.merchant_name ?? tx.bank_merchant_text ?? tx.description_raw;
  const amount = Number(tx.amount);
  return (
    <TableRow onClick={onOpen} className={cn(onOpen && "cursor-pointer")}>
      <TableCell className="max-w-72 whitespace-normal">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
          >
            {name.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            {onOpen ? (
              <button
                type="button"
                className="max-w-full truncate text-left font-medium"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpen();
                }}
              >
                {name}
              </button>
            ) : (
              <p className="truncate font-medium">{name}</p>
            )}
            {tx.note && (
              <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                <StickyNote aria-hidden className="size-3 shrink-0" />
                {tx.note}
              </p>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">
        {tx.level1 ? `${label(tx.level1)} · ${label(tx.category_slug)}` : "Uncategorized"}
      </TableCell>
      <TableCell className="hidden text-xs text-muted-foreground md:table-cell">{tx.account_name}</TableCell>
      {showSource && (
        <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">
          <span className="flex items-center gap-1.5">
            <span aria-hidden className={cn("size-1.5 rounded-full", SOURCE_DOT[tx.category_source] ?? "bg-chart-other")} />
            {sourceLabel(tx.category_source)}
          </span>
        </TableCell>
      )}
      <TableCell className={cn("text-right font-medium", amount > 0 && "text-income")}>
        <span className="inline-flex items-center gap-1.5">
          {tx.is_subscription && <Repeat aria-label="Subscription" className="size-3.5 text-muted-foreground" />}
          {signedMoney(amount)}
        </span>
      </TableCell>
    </TableRow>
  );
}
