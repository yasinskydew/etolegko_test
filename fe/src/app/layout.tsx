import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { ColorModeScript } from "@/components/providers/ColorModeScript";
import { Provider } from "@/components/providers/Provider";

/** Figma `fonts/body` = Inter — single family for heading + body. */
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "etolegko",
  description: "Campaigns, streams, and offer weights",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <head>
        <ColorModeScript />
      </head>
      <body className={inter.className}>
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
