"use client";

import { ChevronRight } from "lucide-react";
import { useStickToBottomContext } from "use-stick-to-bottom";

import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { isRefused, rowsLabel, type QueryOutput, type QueryPart } from "@/lib/chat";

/** The queries behind an answer (spec 10): closed by default, each with its SQL and the rows it
 * returned, or its error. The answer itself never names tables or SQL (spec 6). */
export function QueryDisclosure({ queries }: { queries: QueryPart[] }) {
  // Opening it grows the conversation: without this, stick-to-bottom would scroll the queries
  // the user asked to read out of view. Scrolling back down (or the arrow) re-attaches.
  const { stopScroll } = useStickToBottomContext();
  const running = queries.some((query) => query.state !== "output-available");
  const outputs = queries.flatMap((query) => (query.state === "output-available" ? [query.output] : []));
  const failed = outputs.filter((output) => !isRefused(output) && output.error).length;
  const notRun = outputs.filter(isRefused).length;
  const notes = [failed ? `${failed} failed` : "", notRun ? `${notRun} not run` : ""].filter(Boolean).join(", ");
  const count = queries.length === 1 ? "1 query" : `${queries.length} queries`;
  return (
    <details className="group rounded-xl bg-card text-sm">
      <summary onClick={stopScroll} className="flex cursor-pointer list-none items-center gap-2 rounded-xl px-3 py-2 text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
        <ChevronRight aria-hidden className="size-4 shrink-0 transition-transform group-open:rotate-90" />
        {running ? <Spinner /> : null}
        <span>
          {running ? "Running a query…" : `Ran ${count}`}
          {notes ? ` (${notes})` : null}
        </span>
      </summary>
      <ol className="flex flex-col gap-4 px-3 pb-3">
        {queries.map((query, index) => (
          <li key={query.toolCallId} className="flex min-w-0 flex-col gap-2">
            <p className="text-xs font-medium text-muted-foreground">Query {index + 1}</p>
            <pre className="overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed">
              <code>{query.input?.sql}</code>
            </pre>
            {query.state === "output-available" ? <QueryOutputView output={query.output} /> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

function QueryOutputView({ output }: { output: QueryOutput }) {
  if (isRefused(output)) return <p className="text-muted-foreground">Not run: this answer had already used its query limit.</p>;
  if (output.error) return <p className="text-bad">This query failed: {output.error}</p>;
  return (
    <>
      {output.rows.length > 0 ? (
        // The kit's Table wraps itself in an overflow-x-auto box, which is the sticky header's scroll
        // container: that box gets the height limit, so the header stays visible.
        <div className="overflow-hidden rounded-lg bg-background *:data-[slot=table-container]:max-h-72">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {output.columns.map((column, index) => (
                  <TableHead key={index} className="sticky top-0 bg-background normal-case">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {output.rows.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {row.map((value, index) => (
                    <TableCell key={index} className="font-mono text-xs">
                      {value}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">{rowsLabel(output)}</p>
    </>
  );
}
