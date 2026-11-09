import { notFound } from "next/navigation";

/** The component lab does not exist in a production build.
 *
 *  It is a developer bench: every 3D piece on its own with made-up numbers,
 *  notes about rendering bugs, and a licence warning that fires when a
 *  credit is missing. None of that is for a visitor, and a public URL that
 *  reads like a backstage door makes the rest of the site look less
 *  finished than it is. Same guard as the admin and betting segments: in
 *  development it is a pass-through, in the export it is a 404.
 */
export default function LabLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  if (process.env.NODE_ENV !== "development") notFound();
  return <>{children}</>;
}
