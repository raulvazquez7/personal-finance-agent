/** Colour follows the group, never its rank (spec 8.2). Slots come from the API
 * (Overview.group_slots, every expense group by all-time spend), so a period filter never repaints
 * a group: slots 1-8 are hues, 9 and later each get their own grey. */

export const OTHER_COLOR = "var(--chart-other)";

/** The folded "Other" row is no group: its slice is hatched (the pattern lives in BreakdownDonut),
 * and its tooltip key, which cannot paint a pattern, takes the hatch's ground. */
export const FOLDED_FILL = "url(#folded-hatch)";
export const FOLDED_COLOR = "var(--chart-folded)";

export function groupColor(level1: string | null | undefined, slots: Record<string, number>): string {
  const slot = level1 ? slots[level1] : undefined;
  if (!slot) return OTHER_COLOR; // no expense rows ever: not one of the greys
  if (slot <= 8) return `var(--chart-${slot})`;
  return `var(--chart-grey-${Math.min(slot - 8, 8)})`;
}

/** The one-hue ramp inside a group page, darkest = largest; the 6th step also paints "_other". */
export const rampColor = (index: number) => `var(--ramp-${Math.min(index, 5) + 1})`;
