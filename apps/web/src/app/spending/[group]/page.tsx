import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownGroup, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** A spending group (spec 7.1): its categories as a treemap + table, top merchants, rows. */
export default async function GroupPage({ params, searchParams }: PageProps<"/spending/[group]">) {
  const [{ group }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group })),
  ]);
  if (!knownGroup(group, categories)) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(group)}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: label(group) }]}
      childDimension="category"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group })}
    />
  );
}
