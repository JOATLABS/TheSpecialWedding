"use client";
import React, { useEffect, useRef, useCallback } from "react";

interface InfiniteScrollWrapperProps {
  /** Render prop — receives `true` for the clone copy (skip heavy animations) */
  children: (isClone: boolean) => React.ReactNode;
  /** Called whenever the primary content height is measured (for parallax sync) */
  onPrimaryHeight?: (height: number) => void;
  /** Shared ref that always holds the normalised (modulo'd) scroll position.
   *  Written here on every scroll tick so that the parallax background layer
   *  can read the *exact* same value — zero chance of a 1-frame desync. */
  normalizedScrollRef?: React.MutableRefObject<number>;
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
export default function InfiniteScrollWrapper({
  children,
  onPrimaryHeight,
  normalizedScrollRef,
}: InfiniteScrollWrapperProps) {
  const primaryRef = useRef<HTMLDivElement>(null);
  const resetting = useRef(false);
  const lastHeight = useRef(0);

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

  /* ── report primary height to parent (for parallax sync) ── */
  useEffect(() => {
    if (!primaryRef.current || !onPrimaryHeight) return;

    const report = () => {
      const h = primaryRef.current?.offsetHeight ?? 0;
      if (h > 0 && h !== lastHeight.current) {
        lastHeight.current = h;
        onPrimaryHeight(h);
      }
    };

    // Measure after first paint and on resize / dynamic layout shifts
    report();
    const ro = new ResizeObserver(report);
    ro.observe(primaryRef.current);
    return () => ro.disconnect();
  }, [onPrimaryHeight]);

  /* ── scroll-position reset ─────────────────────────────── */
  const onScroll = useCallback(() => {
    if (resetting.current || !primaryRef.current) return;

    const h = primaryRef.current.offsetHeight;
    if (h === 0) return;

    // Always write the normalised scroll position so the parallax
    // background reads the correct value on every single frame.
    if (normalizedScrollRef) {
      normalizedScrollRef.current = h > 0 ? window.scrollY % h : window.scrollY;
    }

    if (window.scrollY >= h) {
      resetting.current = true;

      // Modulo keeps position consistent even if the user scrolled
      // extremely fast through the clone.
      const target = window.scrollY % h;

      // Use the synchronous, non-animated scrollTo so there is
      // zero delay between the current frame and the repositioned frame.
      window.scrollTo({ top: target, behavior: "instant" as ScrollBehavior });

      // Write normalised value again after reset so subsequent
      // readers within the same frame get the correct position.
      if (normalizedScrollRef) {
        normalizedScrollRef.current = target;
      }

      // Single rAF is sufficient — the browser will have
      // committed the new scroll offset by the next frame.
      requestAnimationFrame(() => {
        resetting.current = false;
      });
    }
  }, [normalizedScrollRef]);

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
