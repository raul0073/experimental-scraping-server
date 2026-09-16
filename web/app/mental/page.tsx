export default function MentalPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-[22px] font-semibold tracking-tight">Mental</h1>
      <p className="mt-2 text-[13.5px] text-ink-2">
        A dependability benchmark for players and teams: not who is best, but
        who holds their level when it is level, behind, or protecting a lead.
      </p>

      <div className="mt-6 rounded-xl border border-[#e4d49a] bg-[#fdfaf0] p-5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-[#6b5606]">
          In validation — not published yet
        </div>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
          A ranking becomes a benchmark only when there is evidence it measures
          something real. Three tests have to pass first, and they will be
          published here with their results whether they pass or fail:
        </p>
        <ol className="mt-3 space-y-2 text-[13.5px] text-ink-2">
          <li>
            <strong className="font-semibold text-ink">
              Does it repeat?
            </strong>{" "}
            A dependability score that does not persist from one season to the
            next is measuring luck, not character.
          </li>
          <li>
            <strong className="font-semibold text-ink">
              Does it predict?
            </strong>{" "}
            A high score should tell us something about the next season that we
            did not feed into it.
          </li>
          <li>
            <strong className="font-semibold text-ink">
              Is it more than the table?
            </strong>{" "}
            Players at dominant clubs will score well on any involvement metric.
            The benchmark has to add information beyond team strength, measured
            against a model that knows nothing about it.
          </li>
        </ol>
      </div>

      <p className="mt-6 text-[13px] leading-relaxed text-ink-2">
        The method is bottom-up: every on-ball event is stamped with the score
        state at the moment it happened, so duels, errors and discipline can be
        measured while a side is chasing a game rather than averaged across
        ninety minutes. Team ratings are then compared against the sum of their
        players — and the gap between them is what the collective adds or
        destroys.
      </p>
    </div>
  );
}
