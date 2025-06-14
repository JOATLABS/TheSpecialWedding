import React from "react";
import { ParallaxSlideshow } from "@/components/landing-page/ParallaxSlideshow";
import { HeroSection } from "@/components/landing-page/HeroSection";
import { AnchorNav } from "@/components/landing-page/AnchorNav";
import { LandingLayoutProps } from '@/types/landing';

export const LandingLayout: React.FC<LandingLayoutProps> = ({ wedding, images }) => {
  return (
    <main className="relative w-full min-h-screen">
      {/* Background slideshow */}
      <ParallaxSlideshow images={images} direction="horizontal" interval={7000} />

      {/* Overlay content */}
      <div className="absolute inset-0 z-10 flex flex-col justify-between">
        {/* Navigation Bar */}
        <AnchorNav sections={["rsvp", "gallery", "registry", "faq"]} />

        {/* Hero Section */}
        <HeroSection coupleName={wedding.coupleName} date={wedding.date} />

        {/* Anchored Sections */}
        <div id="rsvp" className="py-24 px-4 bg-white bg-opacity-80 backdrop-blur-sm">
          {/* Placeholder for RSVP form */}
          <h2 className="text-3xl font-bold text-center">RSVP Section</h2>
        </div>

        <div id="gallery" className="py-24 px-4 bg-white bg-opacity-80 backdrop-blur-sm">
          {/* Placeholder for Gallery */}
          <h2 className="text-3xl font-bold text-center">Gallery Section</h2>
        </div>

        <div id="registry" className="py-24 px-4 bg-white bg-opacity-80 backdrop-blur-sm">
          {/* Placeholder for Registry */}
          <h2 className="text-3xl font-bold text-center">Registry Section</h2>
        </div>

        <div id="faq" className="py-24 px-4 bg-white bg-opacity-80 backdrop-blur-sm">
          {/* Placeholder for FAQ */}
          <h2 className="text-3xl font-bold text-center">FAQ Section</h2>
        </div>
      </div>
    </main>
  );
};
