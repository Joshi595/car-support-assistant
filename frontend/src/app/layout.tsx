import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next, Barlow_Semi_Condensed } from "next/font/google";
import "./globals.css";

// Highway-signage geometry for headings and controls; a typeface built for legibility for reading.
const display = Barlow_Semi_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
});
const body = Atkinson_Hyperlegible_Next({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "Northwind Motors customer help",
  description: "Answers about your Northwind: warranty, service, charging, ordering and more, with sources.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
