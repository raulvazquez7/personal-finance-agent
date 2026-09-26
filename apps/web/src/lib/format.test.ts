import { describe, expect, it } from "vitest";

import {
  MINUS,
  compactMoney,
  dayAt,
  dayHeader,
  dayRange,
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
  toNumber,
} from "./format";

// West of Greenwich, 2026-08-01 (UTC) is still 31 July: vitest.config.mts sets TZ=America/Los_Angeles.

describe("money", () => {
  it("formats euros the way the tables and tiles show them", () => {
    expect(money("2184")).toBe("€2,184.00");
    expect(moneyWhole("3250.40")).toBe("€3,250");
    expect(signedMoney("-42.10")).toBe("−€42.10");
    expect(signedMoney("12.34")).toBe("+€12.34");
    expect(signedMoneyWhole(3250)).toBe("+€3,250");
    expect(compactMoney(2400)).toBe("€2.4K");
    expect(money(null)).toBe("€0.00");
  });

  it("reads the API's decimal strings as numbers, and a missing value as 0", () => {
    expect(toNumber("-42.10")).toBe(-42.1);
    expect(toNumber(null)).toBe(0);
    expect(toNumber(undefined)).toBe(0);
  });

  it("writes every negative number with the true minus sign, as the deltas do", () => {
    // Intl writes a hyphen-minus; one sign everywhere, so money and its change never differ.
    expect(MINUS).toBe("\u2212");
    expect(money(-5)).toBe("−€5.00");
    expect(moneyWhole("-3250.40")).toBe("−€3,250");
    expect(signedMoneyWhole(-3250)).toBe("−€3,250");
    expect(compactMoney(-2400)).toBe("−€2.4K");
    expect(rate(-0.052)).toBe("−5.2%");
  });

  it("never writes a minus before a number that rounds to zero", () => {
    // Savings a few cents below zero, and a rate just below zero, show nothing to subtract.
    expect(moneyWhole("-0.40")).toBe("€0");
    expect(money("-0.004")).toBe("€0.00");
    expect(compactMoney(-0.01)).toBe("€0");
    expect(rate(-0.0004)).toBe("0.0%");
  });

  it("formats shares and rates", () => {
    expect(percent(0.3799)).toBe("38%");
    // A refund after its purchase month makes an entry's net negative: shares leave 0-100%.
    expect(percent(1.25)).toBe("125%");
    expect(percent(-0.1)).toBe("−10%");
    // A row that is not zero never reads as nothing.
    expect(percent(0.003)).toBe("<1%");
    expect(percent(0.005)).toBe("1%");
    expect(percent(0)).toBe("0%");
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

  it("names a range of days, with the start's year only across two years", () => {
    expect(dayRange("2026-08-01", "2026-08-31")).toBe("1 Aug – 31 Aug 2026");
    expect(dayRange("2025-12-10", "2026-01-19")).toBe("10 Dec 2025 – 19 Jan 2026");
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
    latest_day: "2026-08-31",
  };

  it("names the filter pill", () => {
    expect(periodLabel({ period: "month", accounts: [] }, "2026-08-20")).toBe("August 2026");
    expect(periodLabel({ period: "month", month: "2026-01", accounts: [] }, "2026-08-20")).toBe("January 2026");
    expect(periodLabel({ period: "month", accounts: [] }, null)).toBe("Latest month");
    expect(periodLabel({ period: "custom", start: "2026-08-10", end: "2026-08-19", accounts: [] }, null)).toBe(
      "10 Aug – 19 Aug 2026",
    );
    expect(periodLabel({ period: "custom", start: "2025-12-10", end: "2026-01-19", accounts: [] }, null)).toBe(
      "10 Dec 2025 – 19 Jan 2026",
    );
  });

  it("names the resolved range and what it is compared with", () => {
    expect(rangeLabel(august)).toBe("August 2026");
    expect(previousLabel(august)).toBe("vs Jul");
    expect(previousLabel(august, "long")).toBe("vs July");
    expect(periodNames(august)).toEqual({ current: "August", previous: "July" });
    expect(rangeLabel({ ...august, name: "last_3_months", start: "2026-06-01" })).toBe("1 Jun – 31 Aug 2026");
    expect(rangeLabel({ ...august, name: "last_12_months", start: "2025-09-01" })).toBe("1 Sept 2025 – 31 Aug 2026");
    expect(previousLabel({ ...august, name: "last_3_months" })).toBe("vs the 3 months before");
    expect(previousLabel({ ...august, name: "last_12_months" })).toBe("vs the 12 months before");
    expect(previousLabel({ ...august, name: "ytd" })).toBe("vs the same dates last year");
    const tenDays = {
      name: "custom",
      start: "2026-08-10",
      end: "2026-08-19",
      previous_start: "2026-07-31",
      previous_end: "2026-08-09",
      latest_day: "2026-08-20",
    };
    expect(previousLabel(tenDays)).toBe("vs the 10 days before");
    expect(periodNames({ ...august, name: "ytd" })).toEqual({ current: "This period", previous: "Previous period" });
  });

  it("says when the data ends inside the period and the previous one is cut at the same day", () => {
    // Data to 10 August: 1-10 August against 1-10 July (the API's until_same_day).
    const cut = { ...august, previous_end: "2026-07-10", latest_day: "2026-08-10" };
    expect(previousLabel(cut)).toBe("vs Jul by the same day");
    expect(previousLabel(cut, "long")).toBe("vs July by the same day");
    expect(previousLabel({ ...cut, name: "last_3_months", start: "2026-06-01" })).toBe(
      "vs the 3 months before by the same day",
    );
    // Data that ends on 15 August cuts the previous range at as many days: still the 10 days before.
    const tenDays = { name: "custom", start: "2026-08-10", end: "2026-08-19", previous_start: "2026-07-31" };
    expect(previousLabel({ ...tenDays, previous_end: "2026-08-05", latest_day: "2026-08-15" })).toBe(
      "vs the 10 days before by the same day",
    );
    // The first day counts as inside; the last day means the data covers the period whole.
    expect(previousLabel({ ...cut, latest_day: "2026-08-01" })).toBe("vs Jul by the same day");
  });

  it("leaves the suffix off year to date, whose label already names the same dates", () => {
    const ytd = { ...august, name: "ytd", start: "2026-01-01", previous_start: "2025-01-01", previous_end: "2025-08-10" };
    expect(previousLabel({ ...ytd, latest_day: "2026-08-10" })).toBe("vs the same dates last year");
    expect(previousLabel({ ...august, previous_end: "2026-07-10", latest_day: "2026-08-10" })).toBe("vs Jul by the same day");
  });

  it("counts one day in the singular", () => {
    const oneDay = { name: "custom", start: "2026-08-04", end: "2026-08-04", previous_start: "2026-08-03", previous_end: "2026-08-03" };
    expect(previousLabel({ ...oneDay, latest_day: "2026-08-31" })).toBe("vs the 1 day before");
  });

  it("keeps the plain label when the data covers the period whole", () => {
    expect(previousLabel({ ...august, latest_day: "2026-08-31" })).toBe("vs Jul");
    expect(previousLabel({ ...august, latest_day: "2026-09-20" })).toBe("vs Jul");
    expect(previousLabel({ ...august, latest_day: "2026-07-20" })).toBe("vs Jul");
    expect(previousLabel({ ...august, latest_day: null })).toBe("vs Jul");
  });
});
