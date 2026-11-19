import type { Metadata } from "next";
import { Source_Sans_3, Source_Serif_4 } from "next/font/google";

import { ColorModeScript } from "@/components/providers/ColorModeScript";
import { Provider } from "@/components/providers/Provider";

const bodyFont = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-body",
});

const headingFont = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-heading",
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
    <html lang="en" suppressHydrationWarning className={`${bodyFont.variable} ${headingFont.variable}`}>
      <head>
        <ColorModeScript />
      </head>
      <body>
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
