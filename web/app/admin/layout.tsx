import { notFound } from "next/navigation";

/** The admin panel does not exist in a production build.
 *
 *  THE COMPONENT-LEVEL GUARD WAS NOT ENOUGH. Returning "development only"
 *  from the page still emits admin.html into out/, still ships the panel's
 *  JavaScript, and still tells anyone who finds the URL that an admin
 *  surface exists and what it is called. None of that is dangerous on its
 *  own — the endpoints it drives refuse every caller that is not localhost —
 *  but a page whose whole job is starting processes has no business being
 *  discoverable on a public site.
 *
 *  notFound() during the static export means the route is never emitted at
 *  all: no HTML, no chunk, nothing to find. In development it is untouched.
 */
export default function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  if (process.env.NODE_ENV !== "development") notFound();
  return <>{children}</>;
}
