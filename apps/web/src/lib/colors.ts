/** Colour follows the group, never its rank (spec 7.2). Slots 1-5 come from the API
 * (Overview.group_slots, by all-time spend), so a period filter never repaints a group. Every
 * other group is drawn in the "other" grey, with its own row and slice on the overview. */

export const OTHER_COLOR = "var(--chart-other)";

export function groupColor(level1: string | null | undefined, slots: Record<string, number>): string {
  const slot = level1 ? slots[level1] : undefined;
  return slot ? `var(--chart-${slot})` : OTHER_COLOR;
}

/** The one-hue ramp inside a group page, darkest = largest; the 6th step also paints "_other". */
export const rampColor = (index: number) => `var(--ramp-${Math.min(index, 5) + 1})`;
