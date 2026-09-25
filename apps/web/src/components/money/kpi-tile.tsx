import Link from "next/link";

import { Card, CardAction, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import type { Delta } from "@/lib/delta";
import { cn } from "@/lib/utils";

import { DeltaText } from "./delta-text";
import { InfoTip } from "./info-tip";

type Props = {
  label: string;
  definition: string;
  value: string;
  delta: Delta;
  versus: string;
  href?: string;
  income?: boolean;
  hasData?: boolean;
};

/** One of the four overview numbers (spec 7.1): the value, its change against the previous period
 * and an ⓘ with its definition. Income is green with a "+" (spec 7.2). A period without data
 * reads "—" with no delta, never 0 (spec 2.6, Decision G). */
export function KpiTile({ label, definition, value, delta, versus, href, income = false, hasData = true }: Props) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs tracking-wide uppercase">
          {href ? (
            <Link href={href} className="hover:text-foreground">
              {label}
            </Link>
          ) : (
            label
          )}
        </CardDescription>
        <CardAction>
          <InfoTip label={label} text={definition} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <p className={cn("text-2xl font-semibold tracking-tight", income && hasData && "text-income")}>
          {hasData ? value : "—"}
        </p>
        <p className="min-h-4 text-xs text-muted-foreground">
          {hasData && delta.kind !== "hidden" && (
            <>
              <DeltaText value={delta} /> {versus}
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}
