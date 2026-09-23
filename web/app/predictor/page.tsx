"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** The predictor moved to "/". This route stays so that bookmarks and any
 *  link written before the move still land on the thing they meant.
 *
 *  A REDIRECT RATHER THAN A SECOND COPY OF THE PAGE. Rendering PredictorPage
 *  here as well would put it inside the predictor layout, which supplies its
 *  own "Predictor" heading — so the page would carry two <h1>s and the same
 *  content would live at two addresses. One canonical URL, and this one
 *  forwards to it.
 */
export default function PredictorMoved() {
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
