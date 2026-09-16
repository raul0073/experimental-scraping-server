export default function VizPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-[22px] font-semibold tracking-tight">Visualiser</h1>
      <p className="mt-2 text-[13.5px] text-ink-2">
        The raw events, on a real pitch, in three dimensions.
      </p>

      <div className="mt-6 rounded-xl border border-line bg-card p-5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
          In build
        </div>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
          Shots first: every attempt of the round placed on a pitch you can
          orbit, sized by chance quality. Click one and the camera swings behind
          the striker to show what he actually saw — the angle, the distance,
          the block, and the exact corner the ball finished in.
        </p>
        <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
          Then passes that created chances, then duels. One scene per week, the
          same scenes refreshed with each new round.
        </p>
      </div>
    </div>
  );
}
