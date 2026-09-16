import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Predictorous",
  description:
    "A football model that publishes what it expects, what happened, and what it learned.",
};

const NAV = [
  { href: "/predictor", label: "Predictor" },
  { href: "/mental", label: "Mental" },
  { href: "/viz", label: "Visualiser" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-6xl items-baseline gap-8 px-6 py-4">
            <Link href="/" className="text-[17px] font-semibold tracking-tight">
              Predictorous
            </Link>
            <nav className="flex gap-5 text-[14px]">
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
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-6 pb-12 pt-6 text-[12.5px] text-ink-3">
          Probabilities and fair prices only — never betting advice. Data:
          Understat and fbref, with limits stated on each metric.
        </footer>
      </body>
    </html>
  );
}
