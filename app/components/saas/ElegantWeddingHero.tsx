'use client';

import React, { useRef, useState } from 'react';

// Professional wedding-themed 3D card with research-based values
function Card3D({
  children,
  className = "",
  delay = 0
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [rotation, setRotation] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;

    const card = cardRef.current;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    // Limit to 8 degrees max for professional look (not 30+ like before)
    const rotateX = ((y - centerY) / centerY) * -8;
    const rotateY = ((x - centerX) / centerX) * 8;

    setRotation({ x: rotateX, y: rotateY });
  };

  const handleMouseLeave = () => {
    setRotation({ x: 0, y: 0 });
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={`wedding-card ${className}`}
      style={{
        transform: `perspective(1000px) rotateX(${rotation.x}deg) rotateY(${rotation.y}deg) translateZ(0)`,
        transition: rotation.x === 0 ? 'transform 0.6s cubic-bezier(0.23, 1, 0.32, 1)' : 'none',
        animationDelay: `${delay}s`,
      }}
    >
      <div className="card-glow" />
      <div className="card-content">
        {children}
      </div>
    </div>
  );
}

// Elegant SVG petal system (not emoji garbage)
function FallingPetals() {
  // Only 8 petals - professional sites use 8-12 max
  const petals = Array.from({ length: 8 }, (_, i) => ({
    id: i,
    left: `${(i + 1) * 12}%`,
    delay: i * 1.5,
    duration: 8 + (i % 3) * 2,
    swayDelay: i * 0.5,
  }));

  return (
    <div className="petals-container" aria-hidden="true">
      {petals.map((petal) => (
        <div
          key={petal.id}
          className="petal"
          style={{
            left: petal.left,
            animationDelay: `${petal.delay}s, ${petal.swayDelay}s`,
            animationDuration: `${petal.duration}s, 4s`,
          }}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path
              d="M5 0C5 0 0 2.5 0 5C0 7.5 2.5 10 5 10C7.5 10 10 7.5 10 5C10 2.5 5 0 5 0Z"
              fill="url(#petalGradient)"
              opacity="0.6"
            />
            <defs>
              <linearGradient id="petalGradient" x1="0" y1="0" x2="10" y2="10">
                <stop offset="0%" stopColor="#FFB6C1" />
                <stop offset="100%" stopColor="#FFF0F5" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      ))}
    </div>
  );
}

export default function ElegantWeddingHero() {
  const [rsvpCount, setRsvpCount] = useState(0);
  const [guestCount, setGuestCount] = useState(0);

  React.useEffect(() => {
    // Smooth counter animation
    const rsvpTimer = setInterval(() => {
      setRsvpCount((prev) => (prev >= 342 ? 342 : prev + 17));
    }, 50);

    const guestTimer = setInterval(() => {
      setGuestCount((prev) => (prev >= 487 ? 487 : prev + 24));
    }, 50);

    return () => {
      clearInterval(rsvpTimer);
      clearInterval(guestTimer);
    };
  }, []);

  return (
    <div className="elegant-hero-container">
      <FallingPetals />

      <div className="hero-content">
        {/* Main headline and CTA - Center stage */}
        <div className="hero-center">
          <h1 className="hero-headline">
            Your Dream Wedding,
            <br />
            <span className="gradient-text">Perfectly Planned</span>
          </h1>
          <p className="hero-description">
            Manage guests, vendors, and every detail in one beautiful platform.
            From RSVP to the big day.
          </p>
          <div className="hero-cta">
            <button className="btn-primary">
              Start Planning Free
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M7 4L13 10L7 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button className="btn-secondary">Watch Demo</button>
          </div>
        </div>

        {/* Supporting stats - Asymmetric layout for visual interest */}
        <div className="stats-container">
          <Card3D className="stat-card stat-primary" delay={0.2}>
            <div className="stat-value">{rsvpCount}+</div>
            <div className="stat-label">Happy Couples</div>
          </Card3D>

          <Card3D className="stat-card stat-secondary" delay={0.4}>
            <div className="stat-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="#10b981" strokeWidth="2" fill="none" />
                <path d="M8 12L11 15L16 10" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="stat-value">{guestCount}</div>
            <div className="stat-label">Guests Managed</div>
          </Card3D>

          <Card3D className="stat-card stat-accent" delay={0.6}>
            <div className="stat-label">Average Rating</div>
            <div className="rating-display">
              <span className="rating-value">4.9</span>
              <div className="stars">★★★★★</div>
            </div>
          </Card3D>
        </div>
      </div>

      <style jsx>{`
        .elegant-hero-container {
          position: relative;
          width: 100%;
          min-height: 550px;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          background: linear-gradient(135deg, #FFF8F0 0%, #FFF0E5 50%, #FFE4D6 100%);
          padding: 4rem 2rem;
        }

        .hero-content {
          max-width: 1200px;
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 3rem;
        }

        /* Center headline and CTA */
        .hero-center {
          text-align: center;
          max-width: 700px;
        }

        .hero-headline {
          font-size: clamp(2.5rem, 5vw, 3.5rem);
          font-weight: 700;
          line-height: 1.1;
          color: #6B4E3D;
          margin-bottom: 1.5rem;
        }

        .gradient-text {
          background: linear-gradient(135deg, #C4A57B 0%, #D4AF37 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .hero-description {
          font-size: 1.25rem;
          color: #8B7355;
          margin-bottom: 2rem;
          line-height: 1.6;
        }

        .hero-cta {
          display: flex;
          gap: 1rem;
          justify-content: center;
          flex-wrap: wrap;
        }

        .btn-primary, .btn-secondary {
          padding: 1rem 2rem;
          border-radius: 12px;
          font-weight: 600;
          font-size: 1rem;
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
        }

        .btn-primary {
          background: linear-gradient(135deg, #C4A57B 0%, #D4AF37 100%);
          color: white;
          border: none;
          box-shadow: 0 4px 20px rgba(196, 165, 123, 0.4);
        }

        .btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 30px rgba(196, 165, 123, 0.5);
        }

        .btn-secondary {
          background: rgba(255, 255, 255, 0.5);
          backdrop-filter: blur(12px);
          color: #6B4E3D;
          border: 1px solid rgba(196, 165, 123, 0.3);
        }

        .btn-secondary:hover {
          background: rgba(255, 255, 255, 0.7);
          transform: translateY(-2px);
        }

        /* Stats container - asymmetric for visual interest */
        .stats-container {
          display: flex;
          gap: 1.5rem;
          justify-content: center;
          flex-wrap: wrap;
        }

        .stat-card {
          min-width: 200px;
        }

        .stat-primary {
          padding: 2rem;
        }

        .stat-value {
          font-size: 3rem;
          font-weight: 700;
          color: #6B4E3D;
          line-height: 1;
          margin-bottom: 0.5rem;
        }

        .stat-label {
          font-size: 0.875rem;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #A89080;
        }

        .stat-icon {
          margin-bottom: 1rem;
        }

        .rating-display {
          display: flex;
          align-items: baseline;
          gap: 0.75rem;
          margin-top: 0.5rem;
        }

        .rating-value {
          font-size: 2.5rem;
          font-weight: 700;
          color: #6B4E3D;
        }

        .stars {
          color: #D4AF37;
          font-size: 1.25rem;
          letter-spacing: 0.1em;
        }

        /* Falling petals - subtle and elegant */
        .petals-container {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }

        @keyframes fall {
          0% {
            transform: translateY(-10vh) rotate(0deg);
            opacity: 0.8;
          }
          80% {
            opacity: 0.6;
          }
          100% {
            transform: translateY(110vh) rotate(360deg);
            opacity: 0;
          }
        }

        @keyframes sway {
          0%, 100% { transform: translateX(0); }
          50% { transform: translateX(30px); }
        }

        .petal {
          position: absolute;
          animation: fall linear infinite, sway ease-in-out infinite;
        }

        /* Wedding card - glassmorphism done RIGHT */
        .wedding-card {
          position: relative;
          padding: 2rem;
          border-radius: 20px;
          background: rgba(255, 255, 255, 0.25);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 215, 180, 0.3);
          box-shadow: 0 8px 32px 0 rgba(139, 99, 76, 0.12);
          transform-style: preserve-3d;
          animation: cardReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) backwards;
        }

        @keyframes cardReveal {
          from {
            opacity: 0;
            transform: perspective(1000px) translateY(40px) scale(0.96);
          }
          to {
            opacity: 1;
            transform: perspective(1000px) translateY(0) scale(1);
          }
        }

        .card-glow {
          position: absolute;
          inset: 0;
          border-radius: 20px;
          background: linear-gradient(
            135deg,
            rgba(255, 255, 255, 0.4) 0%,
            rgba(255, 255, 255, 0) 60%
          );
          opacity: 0;
          transition: opacity 0.6s cubic-bezier(0.23, 1, 0.32, 1);
          pointer-events: none;
        }

        .wedding-card:hover .card-glow {
          opacity: 1;
        }

        .card-content {
          position: relative;
          z-index: 1;
        }

        /* Accessibility */
        @media (prefers-reduced-motion: reduce) {
          .petal,
          .wedding-card {
            animation: none;
          }

          .wedding-card {
            opacity: 1;
            transform: none;
          }
        }

        /* Responsive */
        @media (max-width: 768px) {
          .elegant-hero-container {
            padding: 3rem 1.5rem;
            min-height: 450px;
          }

          .hero-content {
            gap: 2rem;
          }

          .hero-headline {
            font-size: 2.5rem;
            margin-bottom: 1rem;
          }

          .hero-description {
            font-size: 1.125rem;
            margin-bottom: 1.5rem;
          }

          .stats-container {
            gap: 1rem;
          }

          .stat-card {
            min-width: 160px;
          }

          .stat-value {
            font-size: 2.5rem;
          }
        }
      `}</style>
    </div>
  );
}
