import { useEffect, useState } from "react";

/**
 * A hook to auto-cycle through a list of items
 * @param length - total number of items
 * @param interval - time in milliseconds between slides
 */
export function useSlideshow(length: number, interval: number = 7000): number {
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (!length || length <= 1) return;

    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % length);
    }, interval);

    return () => clearInterval(timer);
  }, [length, interval]);

  return currentIndex;
}
