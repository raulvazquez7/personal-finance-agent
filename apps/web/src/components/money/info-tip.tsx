import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";

/** The ⓘ next to a number: its definition, word for word from docs/money-rules.md (spec 7.2).
 * A popover that also opens on hover, not a tooltip: Base UI tooltips are unreachable on touch
 * and with a screen reader, and its docs name this popover for info icons ("Infotips"). */
export function InfoTip({ label, text }: { label: string; text: string }) {
  return (
    <Popover>
      <PopoverTrigger openOnHover render={<Button variant="ghost" size="icon-xs" aria-label={`About ${label}`} />}>
        <Info />
      </PopoverTrigger>
      <PopoverContent className="w-auto max-w-64 text-xs text-pretty">
        {/* Names the dialog for screen readers; the definition is its description. */}
        <PopoverTitle className="sr-only">{label}</PopoverTitle>
        <PopoverDescription>{text}</PopoverDescription>
      </PopoverContent>
    </Popover>
  );
}
