"use client";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

/** A page whose data could not load (usually: the API is not running). `retry` refetches. */
export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>This page could not load</EmptyTitle>
        <EmptyDescription>
          The API did not answer. Check that it is running (from apps/api: uv run task api), then try again.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button onClick={() => retry()}>Try again</Button>
      </EmptyContent>
    </Empty>
  );
}
