import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { groupName, knownGroup } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/spending/[group]">): Promise<Metadata> {
  // The page fetches the same list; Next.js memoizes the same GET within one request.
  const [{ group }, categories] = await Promise.all([params, apiGet<Schemas["CategoryOut"][]>("/categories")]);
  return { title: groupName(group, categories) };
}

/** A spending group (spec 7.1): its categories as a treemap + table, top merchants, rows. */
export default async function GroupPage({ params, searchParams }: PageProps<"/spending/[group]">) {
  const [{ group }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group)) notFound();
  const filters = parseFilters(query);
  const [categories, merchants, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group })),
  ]);
  if (!knownGroup(group, categories)) notFound();
  const name = groupName(group, categories);
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      merchants={merchants}
      filters={filters}
      title={name}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: name }]}
      childDimension="category"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group })}
    />
  );
}
