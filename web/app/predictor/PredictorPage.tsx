import { getRecord, getRound } from "@/lib/data";

import { Calibration } from "./Calibration";
import { Freshness } from "./Freshness";
import { RoundTables } from "./RoundTables";
import { SubNav } from "./SubNav";

/** The front page.
 *
 *  THE SITE IS A PREDICTOR, SO THE PREDICTOR IS THE FRONT PAGE. What was
 *  here before was three tiles offering a predictor, a ratings benchmark and
 *  a visualiser as equal doors — which is an accurate description of the
 *  codebase and a poor description of the product. A rating cannot be wrong;
 *  a prediction is graded every weekend by someone other than us, and every
 *  part of this site worth showing — the record, the calibration, the
 *  rejected experiments — exists only because of that grading. The other two
 *  are how the predictor shows its working, not rival offers.
 *
 *  Rendered from both "/" and "/predictor" so that every link written before
 *  this change still lands somewhere real.
 */
export function PredictorPage() {
  const round = getRound();
  const record = getRecord();

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <section className="max-w-2xl">
          <h1 className="font-display text-[30px] leading-[1.25] tracking-[0.01em]">
            A football model that shows its work.
          </h1>
          <p className="mt-2.5 text-[14px] leading-relaxed text-ink-2">
            A probability and a fair price for every fixture in the big five.
            Every call is recorded before kickoff and graded afterwards —
            including the wrong ones.
          </p>
          {/* How old the data is, said out loud. The silent failure this
              guards against is a scheduled run that did not happen: the
              site keeps serving what it had and looks entirely healthy. */}
          <Freshness generated={round?.generated ?? round?.as_of} />
        </section>
        {/* The sub-nav moved out of the predictor layout and into the page,
            because the page is now also "/" — which does not sit under that
            layout and would otherwise lose the way through to the projected
            tables and the record. */}
        <SubNav />
      </div>

      {record ? (
        <div className="mt-6">
          <Calibration record={record} />
        </div>
      ) : null}

      {!round ? (
        <p className="mt-8 text-ink-2">No round data exported yet.</p>
      ) : (
        <>
          <p className="mt-8 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
            This round, league by league: the model&apos;s probability for each
            result, the outcome it calls, its most likely scoreline, and the{" "}
            <strong className="font-semibold">fair price</strong> beneath each
            percentage — what that result is worth. Above that price there is
            value in it; below it there is not. We never see your book, so the
            comparison is yours to make.
          </p>

          <div className="mt-5">
            <RoundTables round={round} />
          </div>

          <p className="mt-6 text-[12.5px] leading-relaxed text-ink-3">
            Percentages are the model&apos;s probability; the smaller number is
            the fair price (1 ÷ probability). The called outcome is shaded.
            Scorelines are the most likely result given that call, not a
            prediction of the exact score. Played fixtures stay listed until
            the whole round is done.
            {round.as_of ? (
              // Staleness has to be visible. This page once showed a round
              // four days older than the results sitting beside it, and
              // nothing on it said so.
              <> Data as of <span className="num">{round.as_of}</span>.</>
            ) : null}
          </p>
        </>
      )}
    </div>
  );
}
