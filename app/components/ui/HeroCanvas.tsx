"use client";
import React, { useEffect, useRef } from "react";

const palette = [
  [212, 165, 165],
  [232, 196, 106],
  [168, 218, 220],
  [241, 243, 244],
];

function createParticle(width: number, height: number) {
  const velocity = 0.15 + Math.random() * 0.35;
  const drift = (Math.random() - 0.5) * 0.2;
  const size = 80 + Math.random() * 140;
  const color = palette[Math.floor(Math.random() * palette.length)];
  return {
    x: Math.random() * width,
    y: Math.random() * height,
    vx: drift,
    vy: velocity,
    size,
    color,
    alpha: 0.08 + Math.random() * 0.12,
  };
}

export default function HeroCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particles = useRef<ReturnType<typeof createParticle>[]>([]);
  const animationRef = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth * window.devicePixelRatio;
      canvas.height = Math.max(window.innerHeight * 0.6, 480) * window.devicePixelRatio;
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      particles.current = Array.from({ length: 16 }, () =>
        createParticle(canvas.width, canvas.height)
      );
    };

    resize();
    window.addEventListener("resize", resize);

    const render = () => {
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = "lighter";

      particles.current.forEach((particle, index) => {
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.y - particle.size > canvas.height) {
          particles.current[index] = createParticle(canvas.width, canvas.height);
          particles.current[index].y = -particle.size;
        }

        ctx.beginPath();
        const gradient = ctx.createRadialGradient(
          particle.x,
          particle.y,
          particle.size * 0.1,
          particle.x,
          particle.y,
          particle.size
        );
        gradient.addColorStop(0, `rgba(${particle.color.join(",")}, ${particle.alpha})`);
        gradient.addColorStop(1, "rgba(15, 17, 32, 0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(
          particle.x - particle.size,
          particle.y - particle.size,
          particle.size * 2,
          particle.size * 2
        );
      });

      animationRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", resize);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full opacity-80"
    />
  );
}
