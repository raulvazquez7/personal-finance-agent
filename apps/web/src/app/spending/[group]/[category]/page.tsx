import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { categoryName, groupName, knownCategory } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/spending/[group]/[category]">): Promise<Metadata> {
  // The page fetches the same list; Next.js memoizes the same GET within one request.
  const [{ category }, categories] = await Promise.all([params, apiGet<Schemas["CategoryOut"][]>("/categories")]);
  return { title: categoryName(category, categories) };
}

/** A category inside a group (spec 7.1): the same template, with merchants instead of categories. */
export default async function CategoryPage({ params, searchParams }: PageProps<"/spending/[group]/[category]">) {
  const [{ group, category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group) || !isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, merchants, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group, category })),
  ]);
  if (!knownCategory(category, categories, { type: "expense", level1: group })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      merchants={merchants}
      filters={filters}
      title={categoryName(category, categories)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: groupName(group, categories), href: withFilters(`/spending/${group}`, filters) },
        { label: categoryName(category, categories) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group, category })}
    />
  );
}
