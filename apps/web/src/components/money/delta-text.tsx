import type { Delta } from "@/lib/delta";
import { cn } from "@/lib/utils";

const ARROWS = { up: "↗", down: "↘", flat: "—" } as const;
const WORDS = { up: "up", down: "down", flat: "no change" } as const;
const TONES = { good: "text-good", bad: "text-bad", neutral: "text-muted-foreground" } as const;

type Props = { value: Delta; arrow?: boolean; parens?: boolean };

/** A change against the previous period (spec 2.6): the arrow and the sign always carry the
 * meaning; green or red only add to it. Nothing when the previous period has no data. */
export function DeltaText({ value, arrow = true, parens = false }: Props) {
  if (value.kind === "hidden") return null;
  if (value.kind === "new") return <span className="text-muted-foreground">new</span>;
  return (
    <span className={cn(TONES[value.tone])}>
      {arrow && (
        <>
          <span aria-hidden>{ARROWS[value.direction]} </span>
          <span className="sr-only">{WORDS[value.direction]} </span>
        </>
      )}
      {parens ? `(${value.text})` : value.text}
    </span>
  );
}
