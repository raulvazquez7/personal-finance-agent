import { describe, expect, it } from "vitest";

import { groupColor, rampColor } from "./colors";

const slots = { home: 1, shopping: 2, leisure: 3, transport: 4, credit_card: 5 };

describe("colours", () => {
  it("paints a group by its slot, never by its rank", () => {
    expect(groupColor("shopping", slots)).toBe("var(--chart-2)");
    expect(groupColor("health", slots)).toBe("var(--chart-other)");
    expect(groupColor(null, slots)).toBe("var(--chart-other)");
  });

  it("gives slots 6 to 8 a hue and every later slot its own grey", () => {
    const all = { ...slots, health: 6, gifts: 8, education: 9, other: 16, pets: 17 };
    expect(groupColor("health", all)).toBe("var(--chart-6)");
    expect(groupColor("gifts", all)).toBe("var(--chart-8)");
    expect(groupColor("education", all)).toBe("var(--chart-grey-1)");
    expect(groupColor("other", all)).toBe("var(--chart-grey-8)");
    // Eight greys: every later slot shares the last one.
    expect(groupColor("pets", all)).toBe("var(--chart-grey-8)");
  });

  it("steps the ramp and keeps its last step for the rest", () => {
    expect([0, 1, 5, 9].map(rampColor)).toEqual(["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-6)", "var(--ramp-6)"]);
  });
});
