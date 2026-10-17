import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { categoryName, knownCategory } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/income/[category]">): Promise<Metadata> {
  // The page fetches the same list; Next.js memoizes the same GET within one request.
  const [{ category }, categories] = await Promise.all([params, apiGet<Schemas["CategoryOut"][]>("/categories")]);
  return { title: categoryName(category, categories) };
}

/** One income category, with the merchants that paid it. */
export default async function IncomeCategoryPage({ params, searchParams }: PageProps<"/income/[category]">) {
  const [{ category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, merchants, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "income", category })),
  ]);
  if (!knownCategory(category, categories, { type: "income" })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      merchants={merchants}
      filters={filters}
      title={categoryName(category, categories)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: "Income", href: withFilters("/income", filters) },
        { label: categoryName(category, categories) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "income", category })}
    />
  );
}
