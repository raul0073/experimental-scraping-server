/* Crests are mirrored into public/logos by scripts/export_web.py. A missing
   file must never break a row, so every crest is optional and simply absent
   when we have no badge for that club. */

export function Crest({
  src,
  alt,
  size = 18,
}: {
  src?: string;
  alt: string;
  size?: number;
}) {
  if (!src) return null;
  // Plain <img>: next/image's optimiser is disabled under output: "export",
  // and these are already small PNGs served from the same origin.
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      className="inline-block shrink-0 object-contain"
      style={{ width: size, height: size }}
    />
  );
}

export function LeagueHeading({
  src,
  name,
  meta,
}: {
  src?: string;
  name: string;
  meta?: string;
}) {
  return (
    <h2 className="flex items-center gap-2.5 text-[16px] font-semibold">
      <Crest src={src} alt="" size={22} />
      {name}
      {meta ? (
        <span className="text-[12.5px] font-normal text-ink-3">{meta}</span>
      ) : null}
    </h2>
  );
}
