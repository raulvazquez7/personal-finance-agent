import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownCategory, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** One income category, with the merchants that paid it. */
export default async function IncomeCategoryPage({ params, searchParams }: PageProps<"/income/[category]">) {
  const [{ category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "income", category })),
  ]);
  if (!knownCategory(category, categories, { type: "income" })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(category)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: "Income", href: withFilters("/income", filters) },
        { label: label(category) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "income", category })}
    />
  );
}
