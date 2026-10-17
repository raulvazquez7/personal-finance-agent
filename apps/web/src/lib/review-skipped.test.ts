import { describe, expect, it } from "vitest";

import { parseSkipped } from "./review-skipped";

describe("parseSkipped", () => {
  it("reads the skipped card keys", () => {
    expect(parseSkipped('["m:acme","merge:foods"]')).toEqual(["m:acme", "merge:foods"]);
  });

  it.each(["not json", "{}", '"m:acme"', "[1,2]", '["m:acme",null]', "null"])(
    "falls back to nothing skipped on %s",
    (raw) => {
      expect(parseSkipped(raw)).toEqual([]);
    },
  );
});
