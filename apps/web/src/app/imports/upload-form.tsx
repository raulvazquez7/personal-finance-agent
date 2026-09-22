"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_URL, type Schemas } from "@/lib/api";

export function UploadForm() {
  const router = useRouter();
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const files = new FormData(event.currentTarget).getAll("files") as File[];
    const results: string[] = [];
    for (const file of files) {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(`${API_URL}/imports`, { method: "POST", body });
      if (response.ok) {
        const summary = (await response.json()) as Schemas["ImportSummary"];
        results.push(`${file.name}: ${summary.rows_new} new, ${summary.rows_duplicate} duplicate`);
      } else {
        results.push(`${file.name}: ${response.status} ${await response.text()}`);
      }
    }
    setMessages(results);
    setBusy(false);
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Input type="file" name="files" accept="application/pdf" multiple required />
        <Button type="submit" disabled={busy}>{busy ? "Importing…" : "Import"}</Button>
      </div>
      {messages.length > 0 && (
        <ul className="text-sm text-muted-foreground">
          {messages.map((message) => <li key={message}>{message}</li>)}
        </ul>
      )}
    </form>
  );
}
