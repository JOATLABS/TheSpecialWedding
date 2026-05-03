"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

const HeroAurora = dynamic(() => import("@/components/ui/HeroAurora"), {
  ssr: false,
});
const HeroCanvas = dynamic(() => import("@/components/ui/HeroCanvas"), {
  ssr: false,
});

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

export function DeferredHomeEffects() {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const inViewRef = useRef(false);
  const idleHandleRef = useRef<number | null>(null);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const win = window as IdleWindow;
    const reducedMotion = win.matchMedia("(prefers-reduced-motion: reduce)");

    if (reducedMotion.matches) {
      return undefined;
    }

    const clearScheduledEnable = () => {
      if (idleHandleRef.current !== null && win.cancelIdleCallback) {
        win.cancelIdleCallback(idleHandleRef.current);
      }
      if (fallbackTimerRef.current !== null) {
        clearTimeout(fallbackTimerRef.current);
      }
      idleHandleRef.current = null;
      fallbackTimerRef.current = null;
    };

    const requestEnable = () => {
      if (document.hidden || !inViewRef.current) {
        return;
      }
      clearScheduledEnable();
      if (win.requestIdleCallback) {
        idleHandleRef.current = win.requestIdleCallback(() => setEnabled(true), { timeout: 2500 });
        return;
      }
      fallbackTimerRef.current = setTimeout(() => setEnabled(true), 900);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        inViewRef.current = entry.isIntersecting;
        if (entry.isIntersecting) {
          requestEnable();
          return;
        }
        clearScheduledEnable();
        setEnabled(false);
      },
      { rootMargin: "240px 0px", threshold: 0.05 },
    );

    if (hostRef.current) {
      observer.observe(hostRef.current);
    }

    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearScheduledEnable();
        setEnabled(false);
        return;
      }
      requestEnable();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      observer.disconnect();
      clearScheduledEnable();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  return (
    <div ref={hostRef} className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {enabled ? (
        <>
          <HeroAurora />
          <HeroCanvas />
        </>
      ) : null}
    </div>
  );
}
