import type { Coverage } from "@/lib/coverage";
import { cn } from "@/lib/utils";

const DRAW: Record<Coverage, string> = {
  covered: "bg-primary",
  partial: "bg-primary/35",
  gap: "border border-dashed border-chart-previous bg-background",
  outside: "",
};

/** One account-month on the board, and its key in the legend and the popover (spec section 4.2).
 * Decorative: the month buttons and the popover carry the words. */
export function Swatch({ state, className }: { state: Coverage; className?: string }) {
  return <span aria-hidden className={cn("block size-5 shrink-0 rounded-md", DRAW[state], className)} />;
}
