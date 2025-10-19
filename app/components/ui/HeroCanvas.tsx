"use client";
import React, { useEffect, useRef } from "react";

type PaletteColor = [number, number, number];

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: PaletteColor;
  alpha: number;
  phase: number;
  swing: number;
  wave: number;
};

const palette: PaletteColor[] = [
  [212, 165, 165],
  [232, 196, 106],
  [168, 218, 220],
  [241, 243, 244],
];

function createParticle(width: number, height: number): Particle {
  const size = 90 + Math.random() * 140;
  return {
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.25,
    vy: 0.12 + Math.random() * 0.28,
    size,
    color: palette[Math.floor(Math.random() * palette.length)],
    alpha: 0.06 + Math.random() * 0.14,
    phase: Math.random() * Math.PI * 2,
    swing: 0.004 + Math.random() * 0.008,
    wave: 20 + Math.random() * 40,
  };
}

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function HeroCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particles = useRef<Particle[]>([]);
  const animationRef = useRef<number>();
  const resizeFrame = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduceMotion = mediaQuery.matches;

    const configureParticles = () => {
      const ratio = window.devicePixelRatio || 1;
      const width = window.innerWidth * ratio;
      const height = Math.max(window.innerHeight * 0.6, 520) * ratio;
      canvas.width = width;
      canvas.height = height;
      canvas.style.width = "100%";
      canvas.style.height = "100%";

      const targetCount = reduceMotion ? 0 : Math.max(14, Math.round((window.innerWidth / 280) * 10));
      particles.current = Array.from({ length: targetCount }, () => createParticle(width, height));
      ctx.clearRect(0, 0, width, height);
    };

    const scheduleResize = () => {
      if (resizeFrame.current) cancelAnimationFrame(resizeFrame.current);
      resizeFrame.current = requestAnimationFrame(() => {
        resizeFrame.current = undefined;
        configureParticles();
      });
    };

    configureParticles();
    window.addEventListener("resize", scheduleResize, { passive: true });

    const render = () => {
      if (reduceMotion) return;
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";

      particles.current.forEach((particle, index) => {
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.phase += particle.swing;
        const driftX = Math.sin(particle.phase) * particle.wave;

        if (particle.y - particle.size > height) {
          particles.current[index] = createParticle(width, height);
          particles.current[index].y = -particle.size;
          return;
        }

        if (particle.x + driftX < -particle.size || particle.x + driftX > width + particle.size) {
          particles.current[index] = createParticle(width, height);
          particles.current[index].y = Math.random() * height * 0.5;
          return;
        }

        const drawX = particle.x + driftX;
        const gradient = ctx.createRadialGradient(
          drawX,
          particle.y,
          particle.size * 0.1,
          drawX,
          particle.y,
          particle.size
        );
        gradient.addColorStop(0, `rgba(${particle.color.join(",")}, ${particle.alpha})`);
        gradient.addColorStop(1, "rgba(10, 14, 28, 0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(drawX - particle.size, particle.y - particle.size, particle.size * 2, particle.size * 2);
      });

      animationRef.current = requestAnimationFrame(render);
    };

    if (!reduceMotion) {
      animationRef.current = requestAnimationFrame(render);
    }

    const handleVisibility = () => {
      if (document.hidden && animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = undefined;
      } else if (!document.hidden && !reduceMotion && !animationRef.current) {
        animationRef.current = requestAnimationFrame(render);
      }
    };

    const handleMotionChange = () => {
      reduceMotion = mediaQuery.matches;
      if (reduceMotion && animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = undefined;
      }
      configureParticles();
      if (!reduceMotion && !animationRef.current && !document.hidden) {
        animationRef.current = requestAnimationFrame(render);
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    mediaQuery.addEventListener("change", handleMotionChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      mediaQuery.removeEventListener("change", handleMotionChange);
      window.removeEventListener("resize", scheduleResize);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      if (resizeFrame.current) cancelAnimationFrame(resizeFrame.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="hero-canvas pointer-events-none absolute inset-0 h-full w-full opacity-80"
    />
  );
}
