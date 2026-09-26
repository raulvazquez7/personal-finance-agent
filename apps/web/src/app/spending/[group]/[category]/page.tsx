import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownCategory, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** A category inside a group (spec 7.1): the same template, with merchants instead of categories. */
export default async function CategoryPage({ params, searchParams }: PageProps<"/spending/[group]/[category]">) {
  const [{ group, category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group) || !isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group, category })),
  ]);
  if (!knownCategory(category, categories, { type: "expense", level1: group })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(category)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: label(group), href: withFilters(`/spending/${group}`, filters) },
        { label: label(category) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group, category })}
    />
  );
}
