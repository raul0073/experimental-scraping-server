import { LabPage } from "./LabPage";

/** The title follows the guard in layout.tsx: in the export the route is a
 *  404, and a 404 titled "Component lab" would still name what is behind
 *  it. Metadata is resolved even when the layout calls notFound(), so it
 *  has to be conditional here as well. */
export function generateMetadata() {
  if (process.env.NODE_ENV !== "development") return {};
  return {
    title: "Component lab — Predictorous",
    description: "Every 3D piece on its own, with synthetic data.",
  };
}

export default function Page() {
  return <LabPage />;
}
