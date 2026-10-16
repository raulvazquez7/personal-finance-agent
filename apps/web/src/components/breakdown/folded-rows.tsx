"use client";

import { useState } from "react";

import { BreakdownTableRow } from "@/components/breakdown/breakdown-table";
import { Button } from "@/components/ui/button";
import type { BreakdownItem } from "@/lib/breakdown";

type Props = { item: BreakdownItem; showShare: boolean; compared: boolean };

/** The folded subtotal and, when open, the rows it holds. Open state stays here, off the donut. */
export function FoldedRows({ item, showShare, compared }: Props) {
  const [open, setOpen] = useState(false);
  const noun = item.name.split(" ").at(-1) ?? "merchants";
  return (
    <>
      <BreakdownTableRow
        item={item}
        showShare={showShare}
        compared={compared}
        extra={
          <div className="mt-0.5">
            <Button
              type="button"
              variant="link"
              size="xs"
              className="h-auto px-0"
              aria-expanded={open}
              onClick={() => setOpen((current) => !current)}
            >
              {open ? "Hide" : `Show ${item.rows.length} ${noun}`}
            </Button>
          </div>
        }
      />
      {open &&
        item.rows.map((child) => (
          <BreakdownTableRow key={child.key} item={child} showShare={showShare} compared={compared} indent />
        ))}
    </>
  );
}
