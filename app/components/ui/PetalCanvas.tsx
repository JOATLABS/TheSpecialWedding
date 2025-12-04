"use client";
import React, { useEffect, useRef } from "react";

type Petal = {
  x: number;
  y: number;
  z: number; // depth 0..1 (0 far, 1 near)
  vx: number;
  vy: number;
  ax: number;
  ay: number;
  angle: number; // rotation
  spin: number; // angular velocity
  tilt: number; // flip phase
  size: number; // base size in px (device pixels)
  tint: number; // 0..1 choose between pink->crimson ranges
};

// Simple pseudo-random by seed for stable init
const rand = (seed: number) => {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
};

function createPetal(width: number, height: number, i: number): Petal {
  const z = 0.35 + rand(i + 1) * 0.65; // depth
  const size = (18 + rand(i + 2) * 24) * (0.8 + z * 0.8);
  return {
    x: rand(i + 3) * width,
    y: -rand(i + 4) * height * 0.4 - size,
    z,
    vx: (rand(i + 5) - 0.5) * 0.3,
    vy: 0.4 + rand(i + 6) * 0.6,
    ax: 0,
    ay: 0.002 + z * 0.008, // gravity varies with depth
    angle: rand(i + 7) * Math.PI * 2,
    spin: (rand(i + 8) - 0.5) * 0.02,
    tilt: rand(i + 9) * Math.PI * 2,
    size,
    tint: rand(i + 10),
  };
}

function drawPetalSprite(size: number, tint: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  // generous sprite to rotate without clipping
  const pad = size * 1.2;
  c.width = c.height = Math.ceil(pad * 2);
  const ctx = c.getContext("2d")!;

  ctx.translate(c.width / 2, c.height / 2);

  // Build a teardrop/rose-petal path with subtle serration
  const w = size, h = size * 1.4;
  ctx.beginPath();
  ctx.moveTo(0, -h * 0.45);
  ctx.bezierCurveTo(w * 0.6, -h * 0.55, w * 0.65, -h * 0.05, 0, h * 0.65);
  ctx.bezierCurveTo(-w * 0.65, -h * 0.05, -w * 0.6, -h * 0.55, 0, -h * 0.45);
  ctx.closePath();

  // Color palette between blush and deep rose
  const hueA = 350; // pinkish
  const hueB = 344; // deeper rose
  const hue = hueA + (hueB - hueA) * tint;
  const grad = ctx.createRadialGradient(-w * 0.15, -h * 0.2, 2, 0, 0, Math.max(w, h));
  grad.addColorStop(0, `hsla(${hue}, 70%, 94%, 0.95)`);
  grad.addColorStop(0.35, `hsla(${hue}, 72%, ${76 - tint * 12}%, 0.98)`);
  grad.addColorStop(0.75, `hsla(${hue}, 78%, ${52 - tint * 10}%, 0.98)`);
  grad.addColorStop(1, `hsla(${hue}, 80%, ${42 - tint * 8}%, 0.0)`);
  ctx.fillStyle = grad;
  ctx.fill();

  // Vein highlight
  ctx.save();
  ctx.rotate(-0.2);
  const vein = ctx.createLinearGradient(-w * 0.05, -h * 0.3, w * 0.05, h * 0.55);
  vein.addColorStop(0, "rgba(255,255,255,0.22)");
  vein.addColorStop(0.5, "rgba(255,255,255,0.05)");
  vein.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = vein;
  ctx.globalCompositeOperation = "lighter";
  ctx.fillRect(-w * 0.15, -h * 0.5, w * 0.3, h * 1.1);
  ctx.restore();

  // Edge shadow
  ctx.globalCompositeOperation = "multiply";
  const shadow = ctx.createLinearGradient(-w, 0, w, 0);
  shadow.addColorStop(0, "rgba(0,0,0,0.14)");
  shadow.addColorStop(0.5, "rgba(0,0,0,0.0)");
  shadow.addColorStop(1, "rgba(0,0,0,0.14)");
  ctx.fillStyle = shadow;
  ctx.fill();

  return c;
}

export default function PetalCanvas({ count = 26 }: { count?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const petals = useRef<Petal[]>([]);
  const sprites = useRef<HTMLCanvasElement[]>([]);
  const rafRef = useRef<number>();
  const resizeRef = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduce = media.matches;

    const setup = () => {
      const ratio = window.devicePixelRatio || 1;
      const w = window.innerWidth * ratio;
      const h = Math.max(window.innerHeight * 0.65, 560) * ratio;
      canvas.width = w;
      canvas.height = h;
      canvas.style.width = "100%";
      canvas.style.height = "100%";

      const target = reduce ? 0 : Math.max(count, Math.min(72, Math.round(window.innerWidth / 22)));
      petals.current = Array.from({ length: target }, (_, i) => createPetal(w, h, i + 1));
      sprites.current = petals.current.map((p) => drawPetalSprite(p.size, p.tint));
      ctx.clearRect(0, 0, w, h);
    };

    const scheduleResize = () => {
      if (resizeRef.current) cancelAnimationFrame(resizeRef.current);
      resizeRef.current = requestAnimationFrame(() => {
        resizeRef.current = undefined;
        setup();
      });
    };

    setup();
    window.addEventListener("resize", scheduleResize, { passive: true });

    let t = 0;
    const render = () => {
      if (reduce) return;
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Layered draw by depth for natural overlap
      const order = petals.current.map((p, i) => [i, p.z] as const).sort((a, b) => a[1] - b[1]);

      // Time-based breeze (smooth, low-frequency) with vertical bias
      t += 0.005;
      const wind = Math.sin(t * 0.45) * 0.05 + Math.sin(t * 0.11) * 0.03;

      for (const [idx] of order) {
        const p = petals.current[idx];
        const sprite = sprites.current[idx];

        // Subtle horizontal drift with friction and clamp
        p.ax = wind * (0.15 + p.z * 0.35);
        p.vx = (p.vx + p.ax) * 0.985;
        const maxVx = 0.35;
        if (p.vx > maxVx) p.vx = maxVx;
        if (p.vx < -maxVx) p.vx = -maxVx;

        // Gravity-driven vertical fall with terminal velocity clamp
        p.vy += p.ay * (0.85 + p.z * 0.55);
        const maxVy = 1.6 + p.z * 0.9;
        if (p.vy > maxVy) p.vy = maxVy;

        p.x += p.vx;
        p.y += p.vy;
        p.angle += p.spin * (0.6 + p.z * 0.8);
        p.tilt += 0.04 + p.z * 0.03; // flip phase controls subtle front/back flip

        // Recycle when below screen or out of bounds (tighter horizontal bounds)
        if (p.y - p.size > h || p.x < -120 || p.x > w + 120) {
          const i = Math.floor(Math.random() * 10000);
          const fresh = createPetal(w, h, i);
          fresh.y = -fresh.size;
          fresh.x = Math.random() * w;
          petals.current[idx] = fresh;
          sprites.current[idx] = drawPetalSprite(fresh.size, fresh.tint);
          continue;
        }

        ctx.save();
        ctx.translate(p.x, p.y);
        // Simulate flip by scaling X with a sine wave and adjust alpha slightly
        const flip = Math.sin(p.tilt);
        const scaleX = 0.85 + Math.abs(flip) * 0.25; // limits
        const scaleY = 0.85 + (1 - Math.abs(flip)) * 0.15;
        ctx.rotate(p.angle + flip * 0.4);
        ctx.scale(scaleX, scaleY);
        ctx.globalAlpha = 0.8 * (0.6 + p.z * 0.4);
        // Soft depth-of-field blur for far petals
        if ((1 - p.z) > 0.5) {
          // simulate blur by drawing scaled slightly larger with lower alpha
          ctx.filter = "blur(0.6px)";
        } else {
          ctx.filter = "none";
        }
        ctx.drawImage(sprite, -sprite.width / 2, -sprite.height / 2);
        ctx.restore();
      }

      rafRef.current = requestAnimationFrame(render);
    };

    if (!reduce) rafRef.current = requestAnimationFrame(render);

    const onVisibility = () => {
      if (document.hidden && rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = undefined;
      } else if (!document.hidden && !reduce && !rafRef.current) {
        rafRef.current = requestAnimationFrame(render);
      }
    };
    const onMotion = () => {
      reduce = media.matches;
      setup();
      if (reduce && rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = undefined;
      } else if (!reduce && !rafRef.current && !document.hidden) {
        rafRef.current = requestAnimationFrame(render);
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    media.addEventListener("change", onMotion);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      media.removeEventListener("change", onMotion);
      window.removeEventListener("resize", scheduleResize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (resizeRef.current) cancelAnimationFrame(resizeRef.current);
    };
  }, [count]);

  return (
    <canvas ref={canvasRef} aria-hidden="true" className="petal-canvas pointer-events-none absolute inset-0 h-full w-full" />
  );
}
