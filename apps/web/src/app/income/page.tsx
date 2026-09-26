import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** Income (spec 7.1): the group template over the income categories. More is good here. */
export default async function IncomePage({ searchParams }: PageProps<"/income">) {
  const filters = parseFilters(await searchParams);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "income" })),
  ]);
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title="Income"
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: "Income" }]}
      childDimension="category"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "income" })}
    />
  );
}
