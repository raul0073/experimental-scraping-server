"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** The redirect itself. Split out of page.tsx so that page.tsx can be a
 *  SERVER component and export metadata — a "use client" file cannot, and
 *  without it this route inherited the site-wide title and was indexed as a
 *  second copy of the front page. */
export function Moved() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <p className="text-[13.5px] text-ink-2">
      The predictor is the front page now —{" "}
      <Link href="/" className="text-home underline underline-offset-2">
        continue
      </Link>
      .
    </p>
  );
}
