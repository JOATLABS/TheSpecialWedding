"use client";
import React from "react";

type PetalStyle = React.CSSProperties & {
  "--drift"?: string;
};

interface RosePetalsProps {
  count?: number;
}

const seeded = (seed: number) => {
  // simple deterministic pseudo-random for stable SSR/CSR
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

export function RosePetals({ count = 24 }: RosePetalsProps) {
  const petals = Array.from({ length: count }, (_, i) => {
    const left = Math.round(seeded(i + 1) * 100);
    const delay = +(seeded(i + 2) * 8).toFixed(2);
    const duration = 8 + Math.round(seeded(i + 3) * 10); // 8s - 18s
    const size = 10 + Math.round(seeded(i + 4) * 10); // 10px - 20px
    const drift = 10 + Math.round(seeded(i + 5) * 30); // 10 - 40px
    return { i, left, delay, duration, size, drift };
  });

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {petals.map(({ i, left, delay, duration, size, drift }) => {
        const style: PetalStyle = {
          left: `${left}%`,
          animationDelay: `${delay}s`,
          animationDuration: `${duration}s`,
        };
        style["--drift"] = `${drift}px`;

        return (
          <span key={i} className="petal" style={style}>
            <span
              className="petal-inner"
              style={{
                width: size,
                height: size * 1.4,
                animationDelay: `${delay}s`,
                animationDuration: `${duration}s`,
              }}
            />
          </span>
        );
      })}
    </div>
  );
}

export default RosePetals;
