"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type LegendItem = { key: string; label: string; color: string; shape?: "box" | "line" };

type Props = { items: LegendItem[]; isolated: string | null; onIsolate: (key: string | null) => void };

/** The legend of a chart with two or more series. Clicking an item shows that series alone and
 * dims the others; clicking it again shows them all. Recharts' own legend cannot do this, so the
 * chart keeps the state and passes `hide` to its series (spec 8, gotcha 5). */
export function LegendButtons({ items, isolated, onIsolate }: Props) {
  return (
    <div role="group" aria-label="Series" className="flex flex-wrap gap-1">
      {items.map((item) => (
        <Button
          key={item.key}
          type="button"
          variant="ghost"
          size="xs"
          aria-pressed={isolated === item.key}
          onClick={() => onIsolate(isolated === item.key ? null : item.key)}
          className={cn("text-muted-foreground", isolated !== null && isolated !== item.key && "opacity-50")}
        >
          <span
            aria-hidden
            className={cn("shrink-0", item.shape === "line" ? "h-0.5 w-3.5 rounded-full" : "size-2.5 rounded-[3px]")}
            style={{ background: item.color }}
          />
          {item.label}
        </Button>
      ))}
    </div>
  );
}
