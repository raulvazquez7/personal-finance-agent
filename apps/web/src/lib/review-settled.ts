import type { Schemas } from "./api";

type Item = Schemas["ReviewItem"];

const merchantCards = (items: Item[], merchantId: string) =>
  items.filter((item) => item.kind === "merchant" && item.merchant?.id === merchantId);

/** Duplicate cards a merge of `sourceId` into `intoId` settles on the server: the source's own (the
 * source is deleted), the survivor's (the merge confirms it) and any that suggested the source. */
const mergeCards = (items: Item[], sourceId: string, intoId: string) =>
  items.filter(
    (item) =>
      item.kind === "merge" &&
      (item.merchant?.id === sourceId || item.merchant?.id === intoId || item.merge?.merchant_id === sourceId),
  );

/** The other cards a merchant's confirm settles, so they leave /review with it (spec 9). The server
 * marks the confirmed merchant as reviewed, which drops its duplicate card; with a merge pick the
 * survivor takes the category, so its category card goes too. */
export function settledByConfirm(items: Item[], merchantId: string, mergeInto: string | null): Item[] {
  if (mergeInto === null) return items.filter((item) => item.key === `merge:${merchantId}`);
  return [...merchantCards(items, mergeInto), ...mergeCards(items, merchantId, mergeInto)];
}

/** The other cards a Yes on a duplicate card settles: the source's category card, whose rows now
 * belong to the survivor and come back under it on the next load, and the merge's duplicate cards. */
export function settledByMerge(items: Item[], card: Item): Item[] {
  if (!card.merchant || !card.merge) return [];
  return [
    ...merchantCards(items, card.merchant.id),
    ...mergeCards(items, card.merchant.id, card.merge.merchant_id).filter((item) => item.key !== card.key),
  ];
}
