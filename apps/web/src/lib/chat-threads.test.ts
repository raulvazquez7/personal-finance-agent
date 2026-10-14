import { describe, expect, it } from "vitest";

import type { Thread } from "./chat";
import { dropThread, moveFirst, patchThread, putFirst, threadTitle } from "./chat-threads";

const thread = (id: string, title: string | null = null): Thread => ({
  id,
  title,
  title_source: title ? "model" : null,
  created_at: "1999-01-31T10:00:00Z",
  updated_at: "1999-01-31T10:00:00Z",
});

describe("thread list", () => {
  const list = [thread("a", "Groceries"), thread("b"), thread("c", "Trips")];

  it("names a thread that has no title yet", () => {
    expect([threadTitle(list[0]), threadTitle(list[1])]).toEqual(["Groceries", "Untitled chat"]);
  });

  it("puts a new thread first, once", () => {
    expect(putFirst(list, thread("d")).map((t) => t.id)).toEqual(["d", "a", "b", "c"]);
    expect(putFirst(list, thread("c", "Holidays")).map((t) => [t.id, t.title])).toEqual([
      ["c", "Holidays"],
      ["a", "Groceries"],
      ["b", null],
    ]);
  });

  it("moves a thread that just answered to the top and ignores unknown ids", () => {
    expect(moveFirst(list, "b").map((t) => t.id)).toEqual(["b", "a", "c"]);
    expect(moveFirst(list, "zz")).toBe(list);
  });

  it("patches a title in place and drops a deleted thread", () => {
    expect(patchThread(list, "b", { title: "Rent" }).map((t) => t.title)).toEqual(["Groceries", "Rent", "Trips"]);
    expect(dropThread(list, "a").map((t) => t.id)).toEqual(["b", "c"]);
  });
});
