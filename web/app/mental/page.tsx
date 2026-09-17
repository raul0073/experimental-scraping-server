import { MentalBoard } from "./MentalBoard";

export default function MentalPage() {
  return (
    <div>
      <h1 className="font-display text-[24px] tracking-[0.01em]">Mental</h1>
      <p className="mt-2 max-w-3xl text-[13.5px] text-ink-2">
        Not who is best — who does the things you decide matter. Every metric
        below is measured from Opta event streams, and{" "}
        <strong className="font-semibold">you set the recipe</strong>: what
        counts as mental for a centre-back is not what counts for a winger, and
        it is not for a model to decide. The weights start somewhere sensible
        and are yours to tear up.
      </p>
      <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
        One rule the page enforces: a metric that cannot reproduce itself from
        one season to the next is measuring luck, not character. Those are
        marked in red and ignored by default — you can switch that off, but the
        colour stays.
      </p>

      <div className="mt-6">
        <MentalBoard />
      </div>
    </div>
  );
}
