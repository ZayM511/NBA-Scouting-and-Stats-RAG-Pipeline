import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Ball Knowledge Oracle · NBA Hybrid RAG",
  description:
    "The Ball Knowledge Oracle — hybrid retrieval over Postgres stats and scouting prose for the 2025-26 NBA season. Unbiased, cited, witty.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <head>
        {/* Preload the intro media so the browser starts fetching them
            during HTML parse, in parallel with the JS bundle. The video has
            its moov atom at the front (faststart), so playback can begin
            as soon as the first chunk arrives. */}
        <link rel="preload" as="image" href="/intro-poster.jpg" />
        <link rel="preload" as="video" href="/intro.mp4" type="video/mp4" />
      </head>
      <body className="min-h-full flex flex-col bg-bg text-text">{children}</body>
    </html>
  );
}
