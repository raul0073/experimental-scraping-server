import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The data changes once a round, not once a request: the Python pipeline
  // writes JSON, this reads it at build time, and `next build` emits a plain
  // out/ folder of HTML, CSS and JS. No Node or Python server in production,
  // so the public site cannot break at 3am.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
