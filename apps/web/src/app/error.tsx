"use client";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

/** A page that could not load. The cause is not known here (the API may be stopped, or a request
 * failed), so the copy names none; `retry` refetches. */
export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle render={<h1 />}>This page could not load</EmptyTitle>
        <EmptyDescription>
          Something went wrong while loading it. Try again; if it keeps happening, check that the API is running
          (from apps/api: uv run task api).
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button onClick={() => retry()}>Try again</Button>
      </EmptyContent>
    </Empty>
  );
}
