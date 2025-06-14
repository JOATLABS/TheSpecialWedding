import React, { useEffect, useState } from "react";
import { GalleryImage } from "@/types/landing";
import { useSlideshow } from "@/hooks/useSlideshow"

// ParallaxSlideshow.tsx

interface ParallaxSlideshowProps {
  images: GalleryImage[];
  direction?: "horizontal" | "vertical";
  interval?: number;
}

export const ParallaxSlideshow: React.FC<ParallaxSlideshowProps> = ({
  images,
  direction = "horizontal",
  interval = 7000,
}) => {
  const current = useSlideshow(images.length, interval);

  if (!images || images.length === 0) {
    return (
      <div className="absolute inset-0 z-0 bg-gray-200 flex items-center justify-center">
        <p className="text-gray-600">No images available</p>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 z-0 overflow-hidden">
      {images.map((img, index) => {
        const isActive = index === current;

        const baseTranslate = direction === "horizontal"
          ? "translate-x-0"
          : "translate-y-0";

        const offscreenTranslate = direction === "horizontal"
          ? "translate-x-full"
          : "translate-y-full";

        const visibilityClasses = isActive
          ? `opacity-100 z-10 ${baseTranslate}`
          : `opacity-0 z-0 ${offscreenTranslate}`;

        return (
          <div
            key={img.key || index}
            className={`absolute inset-0 transition-all duration-1000 ease-in-out ${visibilityClasses}`}
            style={{
              backgroundImage: `url(${img.url})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          />
        );
      })}
    </div>
  );
};