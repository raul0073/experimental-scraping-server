import Link from "next/link";
import { SubNav } from "./SubNav";

export default function PredictorLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <Link href="/predictor">
          <h1 className="font-display text-[24px] tracking-[0.01em]">
            Predictor
          </h1>
        </Link>
        <SubNav />
      </div>
      <div className="mt-5">{children}</div>
    </div>
  );
}
