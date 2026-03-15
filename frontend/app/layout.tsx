import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/components/Providers";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "undata Schema Explorer",
  description: "Browse, search, and contribute neuroscience data elements",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>
          <header className="border-b px-6 py-3">
            <nav className="mx-auto flex max-w-7xl items-center gap-6">
              <Link href="/" className="text-lg font-semibold">
                undata
              </Link>
              <Link href="/elements" className="text-sm text-muted-foreground hover:text-foreground">
                Elements
              </Link>
              <Link href="/add" className="text-sm text-muted-foreground hover:text-foreground">
                Contribute
              </Link>
              <Link href="/migrations" className="text-sm text-muted-foreground hover:text-foreground">
                Migrations
              </Link>
            </nav>
          </header>
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
