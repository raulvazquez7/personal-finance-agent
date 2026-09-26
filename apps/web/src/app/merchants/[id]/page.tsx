import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { detailType, isUuid, parseFilters, withFilters, type SearchParams } from "@/lib/params";

export const dynamic = "force-dynamic";

// The page and its title read the same detail: Next.js memoizes the fetch, so it runs once.
const detailPath = (id: string, query: SearchParams) =>
  withFilters("/spending/detail", parseFilters(query), { type: detailType(query), merchant_id: id });

export async function generateMetadata({ params, searchParams }: PageProps<"/merchants/[id]">): Promise<Metadata> {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  if (!isUuid(id)) return {};
  const detail = await apiGet<Schemas["SpendingDetail"]>(detailPath(id, query));
  return { title: detail.merchant_name ?? undefined };
}

/** A merchant (spec 7.1): the total and its delta, the cumulative line against the previous
 * period by default, and its transactions. Links from the income pages add `?type=income`. */
export default async function MerchantPage({ params, searchParams }: PageProps<"/merchants/[id]">) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  if (!isUuid(id)) notFound();
  const filters = parseFilters(query);
  const type = detailType(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(detailPath(id, query)),
  ]);
  if (detail.merchant_name === null) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={detail.merchant_name}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: detail.merchant_name }]}
      childDimension={null}
      seeAllHref={withFilters("/transactions", filters, { tx_type: type, merchant_id: id })}
      defaultView="cumulative"
    />
  );
}
