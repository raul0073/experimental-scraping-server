"use client";

/** A circled i with a real popover rather than a browser tooltip, because
 *  these explanations are two sentences and a native `title` truncates them,
 *  waits a second before appearing, and cannot be styled. */
export function Info({
  children,
  align = "right",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
}) {
  const place =
    align === "right"
      ? "right-0"
      : align === "left"
        ? "left-0"
        : "left-1/2 -translate-x-1/2";
  return (
    <span className="group relative inline-flex items-center">
      <span
        aria-hidden
        className="ml-0.5 inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-ink-3 text-[9px] font-semibold not-italic leading-none text-ink-3 transition-colors group-hover:border-home group-hover:text-home"
      >
        i
      </span>
      <span
        role="tooltip"
        className={`pointer-events-none absolute top-full z-30 mt-1.5 w-72 rounded-lg border border-line bg-card p-2.5 text-left text-[11.5px] font-normal normal-case leading-relaxed tracking-normal text-ink-2 opacity-0 shadow-lg transition-opacity duration-100 group-hover:opacity-100 ${place}`}
      >
        {children}
      </span>
    </span>
  );
}

