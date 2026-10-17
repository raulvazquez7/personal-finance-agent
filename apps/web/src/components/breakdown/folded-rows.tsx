"use client";

import { ChevronRight } from "lucide-react";
import { useRef, useState } from "react";

import { BreakdownTableRow, treeIndent } from "@/components/breakdown/breakdown-table";
import { Button } from "@/components/ui/button";
import { TableCell, TableRow } from "@/components/ui/table";
import type { BreakdownItem } from "@/lib/breakdown";
import { cn } from "@/lib/utils";

/** From this many children, the open list also ends with "Show less": the toggle is out of sight. */
const LONG = 10;

type Props = { item: BreakdownItem; showShare: boolean; compared: boolean; dotted: boolean };

/** The folded subtotal as a tree row: its name, with a chevron, opens and closes the rows it holds,
 * which follow it indented. Open state stays here, off the donut. */
export function FoldedRows({ item, showShare, compared, dotted }: Props) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const columns = 2 + Number(showShare) + Number(compared);
  const tree = treeIndent(dotted);

  function showLess() {
    setOpen(false);
    // The button that was pressed goes away with the rows: hand focus back to the toggle.
    toggle.current?.focus({ preventScroll: true });
    toggle.current?.scrollIntoView({ block: "nearest" });
  }

  return (
    <>
      <BreakdownTableRow
        item={item}
        showShare={showShare}
        compared={compared}
        dotted={dotted}
        name={
          <button
            ref={toggle}
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((current) => !current)}
            className="-ml-1 inline-flex items-center gap-1 rounded-md pr-1 font-medium outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <ChevronRight aria-hidden className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-90")} />
            {item.name}
          </button>
        }
      />
      {open &&
        item.rows.map((child) => (
          <BreakdownTableRow key={child.key} item={child} showShare={showShare} compared={compared} dotted={dotted} indent />
        ))}
      {open && item.rows.length >= LONG && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={columns} className={tree.cell}>
            <span aria-hidden className={cn("absolute inset-y-0 w-px bg-border", tree.guide)} />
            <Button type="button" variant="link" size="xs" className="h-auto px-0" onClick={showLess}>
              Show less
            </Button>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
