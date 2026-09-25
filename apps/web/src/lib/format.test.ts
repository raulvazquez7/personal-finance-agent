import { describe, expect, it } from "vitest";

import {
  compactMoney,
  dayAt,
  dayHeader,
  dayLong,
  dayShort,
  daysIn,
  money,
  moneyWhole,
  monthLabel,
  monthShort,
  percent,
  periodLabel,
  periodNames,
  previousLabel,
  rangeLabel,
  rate,
  signedMoney,
  signedMoneyWhole,
} from "./format";

// West of Greenwich, 2026-08-01 (UTC) is still 31 July: vitest.config.mts sets TZ=America/Los_Angeles.

describe("money", () => {
  it("formats euros the way the tables and tiles show them", () => {
    expect(money("2184")).toBe("€2,184.00");
    expect(moneyWhole("3250.40")).toBe("€3,250");
    expect(signedMoney("-42.10")).toBe("-€42.10");
    expect(signedMoney("25.19")).toBe("+€25.19");
    expect(signedMoneyWhole(3250)).toBe("+€3,250");
    expect(compactMoney(2400)).toBe("€2.4K");
    expect(money(null)).toBe("€0.00");
  });

  it("formats shares and rates", () => {
    expect(percent(0.3799)).toBe("38%");
    // A refund after its purchase month makes an entry's net negative: shares leave 0-100%.
    expect(percent(1.25)).toBe("125%");
    expect(percent(-0.1)).toBe("-10%");
    expect(rate(0.328)).toBe("32.8%");
    expect(rate(null)).toBe("—");
  });
});

describe("dates are formatted in UTC", () => {
  it("never shows the day before", () => {
    expect(dayHeader("2026-08-01")).toBe("Sat, 1 Aug");
    expect(dayShort("2026-08-31")).toBe("31 Aug");
    expect(dayLong("2026-01-01")).toBe("1 Jan 2026");
    expect(monthLabel("2026-08")).toBe("August 2026");
    expect(monthShort("2026-02")).toBe("Feb");
  });

  it("counts the days of a period", () => {
    expect(dayAt("2026-08-01", 30)).toBe("2026-08-31");
    expect(daysIn("2026-02-01", "2026-02-28")).toBe(28);
  });
});

describe("period labels", () => {
  const august = {
    name: "month",
    start: "2026-08-01",
    end: "2026-08-31",
    previous_start: "2026-07-01",
    previous_end: "2026-07-31",
  };

  it("names the filter pill", () => {
    expect(periodLabel({ period: "month", accounts: [] }, "2026-08-20")).toBe("August 2026");
    expect(periodLabel({ period: "month", month: "2026-01", accounts: [] }, "2026-08-20")).toBe("January 2026");
    expect(periodLabel({ period: "month", accounts: [] }, null)).toBe("Latest month");
    expect(periodLabel({ period: "custom", start: "2026-08-10", end: "2026-08-19", accounts: [] }, null)).toBe(
      "10 Aug – 19 Aug 2026",
    );
  });

  it("names the resolved range and what it is compared with", () => {
    expect(rangeLabel(august)).toBe("August 2026");
    expect(previousLabel(august)).toBe("vs Jul");
    expect(previousLabel(august, "long")).toBe("vs July");
    expect(periodNames(august)).toEqual({ current: "August", previous: "July" });
    expect(rangeLabel({ ...august, name: "last_3_months", start: "2026-06-01" })).toBe("1 Jun – 31 Aug 2026");
    expect(previousLabel({ ...august, name: "last_3_months" })).toBe("vs the 3 months before");
    expect(previousLabel({ ...august, name: "ytd" })).toBe("vs the same dates last year");
    expect(previousLabel({ ...august, name: "custom", previous_start: "2026-07-31", previous_end: "2026-08-09" })).toBe(
      "vs the 10 days before",
    );
    expect(periodNames({ ...august, name: "ytd" })).toEqual({ current: "This period", previous: "Previous period" });
  });
});
