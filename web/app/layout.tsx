import type { Metadata } from "next";
import { Genos, Montserrat, Prosto_One } from "next/font/google";
import Link from "next/link";
import { Nav } from "./components/Nav";
import "./globals.css";

// Self-hosted at build time by next/font: no external request at runtime and
// no layout shift. Each face has one job — Prosto One is display-only (single
// weight, wide), Montserrat carries everything that gets read, and Genos is
// held for the 3D visualiser's overlay labels.
const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--ff-body",
  display: "swap",
});

const prosto = Prosto_One({
  subsets: ["latin"],
  weight: "400",
  variable: "--ff-display",
  display: "swap",
});

const genos = Genos({
  subsets: ["latin"],
  variable: "--ff-accent",
  display: "swap",
});

const SITE = "https://predictorous.com";

/** Built by scripts/build_og_image.py, which is also where the reasoning
 *  lives for why this card states no live figures. Shared by Open Graph and
 *  Twitter rather than kept as two files — nothing about the card is
 *  platform-specific, and one file is one thing to keep current. */
const OG_IMAGE = {
  url: "/og.png",
  width: 1200,
  height: 630,
  alt: "Predictorous - a football model that shows its work. Paired bars "
    + "comparing the probability the model stated against how often that "
    + "outcome actually happened.",
};

export const metadata: Metadata = {
  /** REQUIRED FOR OPEN GRAPH TO RESOLVE. Next builds share-card image URLs
   *  relative to this; without it they come out as bare paths, which no
   *  scraper can fetch, and every link posted anywhere renders as a naked
   *  URL with no preview. */
  metadataBase: new URL(SITE),
  title: {
    default: "Predictorous - a football model that shows its work",
    /** Pages set only their own name; the site name is appended here so no
     *  page has to remember to. */
    template: "%s · Predictorous",
  },
  description:
    "A calibrated match predictor for Europe's big five. Every call is "
    + "recorded before kickoff and graded afterwards — including the wrong ones.",
  applicationName: "Predictorous",
  openGraph: {
    type: "website",
    siteName: "Predictorous",
    url: SITE,
    title: "Predictorous - a football model that shows its work",
    description:
      "Probabilities and fair prices for every fixture in the big five, "
      + "with the record of what was called and what happened.",
    images: [OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "Predictorous - a football model that shows its work",
    description:
      "Probabilities and fair prices for every fixture in the big five, "
      + "with the record of what was called and what happened.",
    images: [OG_IMAGE],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${montserrat.variable} ${prosto.variable} ${genos.variable}`}
    >
      <body className="antialiased">
        <header className="border-b border-line">
          {/* flex-wrap, because at 375px the wordmark and three nav items do
              not fit on one line and a header that does not wrap is a header
              that scrolls the whole page sideways. */}
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-baseline gap-x-5 gap-y-2 px-4 py-4 sm:gap-x-8 sm:px-6">
            <Link
              href="/"
              className="font-display text-[19px] tracking-[0.02em]"
            >
              Predictorous
            </Link>
            <Nav />
          </div>
        </header>
        {/* 16px gutter on a phone, 24 from `sm` up. */}
        <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 sm:py-8">
          {children}
        </main>
        <footer className="mx-auto max-w-[1440px] px-4 pb-12 pt-6 text-[12.5px] text-ink-3 sm:px-6">
          Probabilities and fair prices only — never betting advice. Data:
          Understat and fbref, with limits stated on each metric.
        </footer>
      </body>
    </html>
  );
}
