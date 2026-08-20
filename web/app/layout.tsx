import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codebase → Markdown",
  description:
    "Turn a repository into one markdown document: a rendered directory tree "
    + "plus every source file, fenced and labelled.",
};

export const viewport: Viewport = {
  themeColor: "#171c26",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {/*
          Loaded via <link> rather than next/font so an offline build falls back
          to system faces instead of failing outright.
        */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          href={
            "https://fonts.googleapis.com/css2"
            + "?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,700;12..96,800"
            + "&family=IBM+Plex+Sans:wght@400;500;600"
            + "&family=JetBrains+Mono:wght@400;500"
            + "&display=swap"
          }
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
