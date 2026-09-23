import Link from "next/link";

/** Where you are, and one click back to everywhere above it.
 *
 *  Nine routes now, three of them two or three levels deep, and a team page
 *  is reached by clicking a club in a table — so the only way back used to be
 *  the browser button, which loses the period you had selected.
 *
 *  The trail is passed in rather than parsed out of the pathname. A parsed
 *  trail has to guess: "/team/crystal-palace" would title-case to "Crystal
 *  Palace" but "/team/afc-bournemouth" to "Afc Bournemouth", and the segment
 *  "team" names a folder that is not a page at all. The page knows its own
 *  name and its own parent; a route table would only be a second copy of
 *  that, kept somewhere else, going stale.
 *
 *  Home is prepended. The last item is the current page and is never a link.
 */
export function Crumbs({
  trail,
}: {
  trail: { href?: string; label: string }[];
}) {
  const all = [{ href: "/", label: "Home" }, ...trail];
  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="flex flex-wrap items-center gap-1.5 text-[12.5px] text-ink-3">
        {all.map((c, i) => {
          const last = i === all.length - 1;
          return (
            <li key={`${c.href ?? ""}${c.label}`} className="flex items-center gap-1.5">
              {i > 0 && (
                <span aria-hidden className="text-line select-none">
                  /
                </span>
              )}
              {c.href && !last ? (
                <Link
                  href={c.href}
                  className="transition-colors hover:text-ink hover:underline"
                >
                  {c.label}
                </Link>
              ) : (
                <span
                  className={last ? "font-medium text-ink-2" : undefined}
                  aria-current={last ? "page" : undefined}
                >
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
