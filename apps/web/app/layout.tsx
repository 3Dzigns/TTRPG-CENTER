import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ClientOnly } from "../components/common/client-only";

export const metadata: Metadata = {
  title: "TTRPG Center",
  description: "Role-aware control center for TTRPG campaigns"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-surface-50 text-slate-900 antialiased dark:bg-surface-900 dark:text-slate-50">
        <a href="#main-content" className="skip-to-content">
          Skip to main content
        </a>
        <ClientOnly fallback={<div className="p-6 text-slate-500">Loading application...</div>}>
          <Providers>{children}</Providers>
        </ClientOnly>
      </body>
    </html>
  );
}

