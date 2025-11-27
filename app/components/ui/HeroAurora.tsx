"use client";
import React, { useMemo } from "react";

type AuroraLayer = {
  id: string;
  delay: number;
  duration: number;
  startX: string;
  startY: string;
  endX: string;
  endY: string;
  rotation: string;
  swing: string;
  gradient: string;
  opacity: number;
};

const layersSeed: AuroraLayer[] = [
  {
    id: "primary",
    delay: 0,
    duration: 18,
    startX: "-18%",
    startY: "-6%",
    endX: "12%",
    endY: "8%",
    rotation: "16deg",
    swing: "10deg",
    gradient:
      "radial-gradient(70% 120% at 20% 20%, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.05) 45%, rgba(212,165,165,0.0) 100%), radial-gradient(80% 140% at 80% 50%, rgba(212,165,165,0.65) 0%, rgba(232,196,106,0.15) 45%, rgba(15,17,32,0) 100%)",
    opacity: 0.55,
  },
  {
    id: "secondary",
    delay: 5.2,
    duration: 22,
    startX: "8%",
    startY: "-12%",
    endX: "-10%",
    endY: "10%",
    rotation: "-22deg",
    swing: "14deg",
    gradient:
      "radial-gradient(80% 140% at 30% 10%, rgba(168,218,220,0.5) 0%, rgba(241,243,244,0.05) 55%, rgba(15,17,32,0) 100%), radial-gradient(90% 150% at 75% 80%, rgba(232,196,106,0.4) 0%, rgba(15,17,32,0) 100%)",
    opacity: 0.45,
  },
  {
    id: "accent",
    delay: 2.8,
    duration: 26,
    startX: "-6%",
    startY: "18%",
    endX: "18%",
    endY: "-12%",
    rotation: "8deg",
    swing: "18deg",
    gradient:
      "radial-gradient(70% 120% at 15% 50%, rgba(200,82,130,0.6) 0%, rgba(200,82,130,0.05) 55%, rgba(15,17,32,0) 100%), radial-gradient(120% 180% at 85% 60%, rgba(241,243,244,0.45) 0%, rgba(15,17,32,0) 100%)",
    opacity: 0.4,
  },
];

export default function HeroAurora() {
  const layers = useMemo(() => layersSeed, []);

  return (
    <div className="hero-aurora" aria-hidden="true">
      {layers.map((layer) => (
        <span
          key={layer.id}
          className="hero-aurora__ribbon"
          style={{
            "--delay": `${layer.delay}s`,
            "--duration": `${layer.duration}s`,
            "--start-x": layer.startX,
            "--start-y": layer.startY,
            "--end-x": layer.endX,
            "--end-y": layer.endY,
            "--rotation": layer.rotation,
            "--swing": layer.swing,
            "--opacity": layer.opacity,
            "--gradient": layer.gradient,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
