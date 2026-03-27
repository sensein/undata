import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthProvider } from "@/components/AuthProvider";
import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "undata",
  description: "Universal data element registry for neuroscience",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased bg-gray-50`}>
        <Providers>
          <AuthProvider>
            <Sidebar />
            <main className="md:ml-52 p-6 min-h-screen">{children}</main>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
