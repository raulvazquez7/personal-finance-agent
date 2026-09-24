import { apiGet, type Schemas } from "@/lib/api";

import { ReviewList } from "./review-list";

export const dynamic = "force-dynamic";

export default async function ReviewPage() {
  const [items, categories, merchants] = await Promise.all([
    apiGet<Schemas["ReviewItem"][]>("/review"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
  ]);
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">
      <ReviewList initialItems={items} categories={categories} merchants={merchants} />
    </main>
  );
}
