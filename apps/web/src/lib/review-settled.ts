import type { Schemas } from "./api";

type Item = Schemas["ReviewItem"];

/** A merchant's category cards: its grouped card and its single rows, not its duplicate card. */
const merchantCards = (items: Item[], merchantId: string) =>
  items.filter((item) => item.kind !== "merge" && item.merchant?.id === merchantId);

/** Cards a merge of `sourceId` settles on the server: every card of the source (it is deleted and
 * its rows come back under the survivor on the next load) and the duplicate cards that suggest it.
 * The survivor keeps its own duplicate card: the server keeps that question open. */
const mergedAway = (items: Item[], sourceId: string) =>
  items.filter((item) => item.merchant?.id === sourceId || item.merge?.merchant_id === sourceId);

/** The other cards a merchant card's confirm settles, so they leave /review with it (spec 9).
 * Without a merge pick none: the category and the duplicate are separate questions. With one the
 * survivor takes the category, so its category cards go too. */
export function settledByConfirm(items: Item[], card: Item, mergeInto: string | null): Item[] {
  if (mergeInto === null || !card.merchant) return [];
  return [...merchantCards(items, mergeInto), ...mergedAway(items, card.merchant.id)].filter(
    (item) => item.key !== card.key,
  );
}

/** The other cards a Yes on a duplicate card settles. */
export function settledByMerge(items: Item[], card: Item): Item[] {
  if (!card.merchant) return [];
  return mergedAway(items, card.merchant.id).filter((item) => item.key !== card.key);
}
