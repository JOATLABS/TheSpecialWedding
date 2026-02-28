"use client";
import React, { useEffect, useRef, useCallback } from "react";

interface InfiniteScrollWrapperProps {
  /** Render prop — receives `true` for the clone copy (skip heavy animations) */
  children: (isClone: boolean) => React.ReactNode;
}

/**
 * Infinite-scroll "wheel" wrapper.
 *
 * Renders primary content followed by a lightweight clone.
 * When the user scrolls past the primary into the clone zone,
 * the scroll position resets silently so the top re-appears
 * without any visible jump — like a continuously turning wheel.
 *
 * The clone is `aria-hidden` + `pointer-events:none` so it can't
 * be interacted with and is invisible to screen readers.
 */
export default function InfiniteScrollWrapper({ children }: InfiniteScrollWrapperProps) {
  const primaryRef = useRef<HTMLDivElement>(null);
  const resetting = useRef(false);

  /* ── hide native scrollbar ─────────────────────────────── */
  useEffect(() => {
    const id = "infinite-scroll-hide-scrollbar";
    if (document.getElementById(id)) return;

    const style = document.createElement("style");
    style.id = id;
    style.textContent = [
      "html::-webkit-scrollbar{display:none!important}",
      "html{scrollbar-width:none!important;-ms-overflow-style:none!important}",
    ].join("");
    document.head.appendChild(style);

    return () => {
      style.remove();
    };
  }, []);

  /* ── scroll-position reset ─────────────────────────────── */
  const onScroll = useCallback(() => {
    if (resetting.current || !primaryRef.current) return;

    const h = primaryRef.current.offsetHeight;
    if (h === 0) return;

    if (window.scrollY >= h) {
      resetting.current = true;
      // Modulo keeps position consistent even if the user scrolled
      // extremely fast through the clone.
      window.scrollTo({ top: window.scrollY % h, behavior: "instant" as ScrollBehavior });

      // Double-rAF: let the browser paint the new position before
      // we start listening for scroll events again.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          resetting.current = false;
        });
      });
    }
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [onScroll]);

  return (
    <>
      {/* ─── Primary content (interactive, has IDs, runs canvases) ─── */}
      <div ref={primaryRef}>{children(false)}</div>

      {/* ─── Clone (visual only — no interaction, no IDs, no canvases) ─── */}
      <div
        aria-hidden="true"
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        {children(true)}
      </div>
    </>
  );
}
