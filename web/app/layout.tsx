import type { Metadata } from "next";
import { Genos, Montserrat, Prosto_One } from "next/font/google";
import Link from "next/link";
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

export const metadata: Metadata = {
  title: "Predictorous",
  description:
    "A football model that publishes what it expects, what happened, and what it learned.",
};

const NAV = [
  { href: "/predictor", label: "Predictor" },
  { href: "/mental", label: "Mental" },
  { href: "/viz", label: "Visualiser" },
  { href: "/how-it-works", label: "How it works" },
];

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
          <div className="mx-auto flex max-w-[1440px] items-baseline gap-8 px-6 py-4">
            <Link
              href="/"
              className="font-display text-[19px] tracking-[0.02em]"
            >
              Predictorous
            </Link>
            <nav className="flex gap-5 text-[13.5px]">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="text-ink-2 transition-colors hover:text-ink"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-[1440px] px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-[1440px] px-6 pb-12 pt-6 text-[12.5px] text-ink-3">
          Probabilities and fair prices only — never betting advice. Data:
          Understat and fbref, with limits stated on each metric.
        </footer>
      </body>
    </html>
  );
}
