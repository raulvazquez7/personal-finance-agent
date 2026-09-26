import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { TopBar } from "@/components/shell/top-bar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Each page names itself: "Transactions · tally ai" (WCAG 2.4.2).
  title: { default: "tally ai", template: "%s · tally ai" },
  description: "Local-first personal finance: import bank statements and see where your money goes.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        {/* The first Tab stop: past the logo, the navigation and the filters (WCAG 2.4.1). */}
        <a
          href="#main"
          className="sr-only rounded-full bg-foreground text-sm font-medium text-background focus:not-sr-only focus:fixed focus:top-2 focus:left-4 focus:z-50 focus:px-3 focus:py-1.5"
        >
          Skip to content
        </a>
        <TooltipProvider>
          <TopBar />
          <main id="main" className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-5 sm:px-6">{children}</main>
        </TooltipProvider>
        {/* Light mode only in slice 3: the toaster must not follow a dark system theme. */}
        <Toaster position="bottom-center" theme="light" />
      </body>
    </html>
  );
}
