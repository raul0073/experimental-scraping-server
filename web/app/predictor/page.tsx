import { Moved } from "./Moved";

/** The predictor moved to "/". This route stays so that bookmarks and any
 *  link written before the move still land on the thing they meant.
 *
 *  A REDIRECT RATHER THAN A SECOND COPY OF THE PAGE. Rendering PredictorPage
 *  here as well would put it inside the predictor layout, which supplies its
 *  own "Predictor" heading — so the page would carry two <h1>s and the same
 *  content would live at two addresses. One canonical URL, and this one
 *  forwards to it.
 *
 *  NOINDEX, AND A CANONICAL POINTING HOME. Until now this route had no
 *  metadata of its own, so it inherited the site title verbatim and search
 *  engines saw a second page called "Predictorous — a football model that
 *  shows its work" whose whole content was the word "continue". That is the
 *  textbook way to make a site compete with itself. The canonical says where
 *  the content really lives; the noindex keeps the stub out of the results.
 */
export const metadata = {
  title: "Predictor",
  description: "The predictor now lives on the front page.",
  robots: { index: false, follow: true },
  alternates: { canonical: "/" },
};

export default function PredictorMoved() {
  return <Moved />;
}
