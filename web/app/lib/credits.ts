/** Third-party assets and what their licences require of us.
 *
 *  CC-BY IS A CONTRACT, NOT A COURTESY. Attribution has to name the work,
 *  the author, where it came from and the licence, and it has to be visible
 *  wherever the work is — which is why this is a shared constant rendered
 *  beside the thing it credits rather than a line buried in a README nobody
 *  opens. If an asset is ever swapped out, the credit goes with it.
 *
 *  Nothing under a non-commercial licence belongs here: this site is a
 *  public portfolio piece, and NC would make showing it a breach.
 */
export type Credit = {
  /** what the thing is, in our words */
  what: string;
  /** the work's own title, as the author published it */
  title: string;
  author: string;
  /** the page it came from */
  url: string;
  licence: string;
  licenceUrl: string;
};

/** The player figure on the average-positions map. */
export const MODEL_CREDIT: Credit = {
  what: "Player figure",
  title: "Soccer Player in Yellow Jersey",
  author: "restore50",
  url: "https://sketchfab.com/3d-models/soccer-player-in-yellow-jersey-1101be401961409ebf64001bfc2c7d10",
  licence: "CC Attribution",
  licenceUrl: "https://creativecommons.org/licenses/by/4.0/",
};

export const isComplete = (c: Credit) => !!(c.title && c.author && c.url);
