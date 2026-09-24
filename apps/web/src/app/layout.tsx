import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { Badge } from "@/components/ui/badge";
import { Toaster } from "@/components/ui/sonner";
import { reviewCount } from "@/lib/api";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "personal-finance-agent",
  description: "Local-first personal finance assistant: import bank statements and browse transactions.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const pending = await reviewCount();
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b">
          <nav className="mx-auto flex max-w-5xl gap-6 p-4 text-sm font-medium">
            <Link href="/imports">Imports</Link>
            <Link href="/transactions">Transactions</Link>
            <Link href="/review" className="flex items-center gap-2">
              Review
              {pending ? <Badge variant="secondary" className="tabular-nums">{pending}</Badge> : null}
            </Link>
          </nav>
        </header>
        {children}
        <Toaster position="bottom-center" />
      </body>
    </html>
  );
}
