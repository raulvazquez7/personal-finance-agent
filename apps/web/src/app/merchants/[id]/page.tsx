import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { MerchantControls } from "@/components/merchants/merchant-controls";
import { ApiError, apiGet, type Schemas } from "@/lib/api";
import {
  detailType,
  isUuid,
  needsDefaultPeriod,
  parseFilters,
  replaceParams,
  withFilters,
  type SearchParams,
} from "@/lib/params";

export const dynamic = "force-dynamic";

// The page and its title read the same detail: Next.js memoizes the fetch, so it runs once.
const detailPath = (id: string, query: SearchParams) =>
  withFilters("/spending/detail", parseFilters(query), { type: detailType(query), merchant_id: id });

export async function generateMetadata({ params, searchParams }: PageProps<"/merchants/[id]">): Promise<Metadata> {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  // The page redirects these: no need to read the detail twice.
  if (!isUuid(id) || needsDefaultPeriod(query)) return {};
  const detail = await apiGet<Schemas["SpendingDetail"]>(detailPath(id, query));
  return { title: detail.merchant_name ?? undefined };
}

/** A merchant (spec 7.1, 7): its controls, the total and its delta, the cumulative line against
 * the previous period by default, and its transactions. Links from the income pages add
 * `?type=income`. Without a period it shows 12 months, every other param kept. */
export default async function MerchantPage({ params, searchParams }: PageProps<"/merchants/[id]">) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  if (!isUuid(id)) notFound();
  if (needsDefaultPeriod(query)) redirect(`/merchants/${id}?${replaceParams("", { ...query, period: "last_12_months" })}`);
  const filters = parseFilters(query);
  const type = detailType(query);
  const [categories, merchants, detail, profile] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
    apiGet<Schemas["SpendingDetail"]>(detailPath(id, query)),
    // An unknown id is a 404 page; any other failure stays an error.
    apiGet<Schemas["MerchantProfile"]>(`/merchants/${id}`).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }),
  ]);
  if (detail.merchant_name === null || profile === null) notFound();
  return (
    <DetailPage
      controls={
        <MerchantControls
          key={profile.id}
          profile={profile}
          categories={categories}
          merchants={merchants}
          direction={type === "income" ? "in" : "out"}
        />
      }
      detail={detail}
      categories={categories}
      merchants={merchants}
      filters={filters}
      title={detail.merchant_name}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: detail.merchant_name }]}
      childDimension={null}
      seeAllHref={withFilters("/transactions", filters, { tx_type: type, merchant_id: id })}
      defaultView="cumulative"
    />
  );
}
