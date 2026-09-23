"use client";

import { Component, type ReactNode } from "react";

/** Catches anything thrown inside a 3D scene and says so.
 *
 *  A WebGL canvas that fails renders NOTHING — a black rectangle, identical
 *  to one that is simply still loading, with the real error only in the
 *  console. That is how "it shows for a second and crashes" ends up being
 *  all anyone can report. A boundary turns the black box into a sentence.
 */
export class SceneGuard extends Component<
  { children: ReactNode; label?: string },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 p-6 text-center">
          <span className="text-[13px] font-semibold text-white/90">
            {this.props.label ?? "This scene failed to draw."}
          </span>
          <code className="max-w-lg text-[11.5px] leading-relaxed text-white/55">
            {this.state.error.message}
          </code>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-1 rounded-full border border-white/25 px-3 py-0.5 text-[12px] text-white/80 hover:border-white/50"
          >
            try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
