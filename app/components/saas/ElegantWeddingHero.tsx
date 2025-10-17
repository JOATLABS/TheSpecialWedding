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

      {/* Center focal point - simplified, not chaotic */}
      <div className="hero-grid">
        {/* RSVP Counter - Top Left */}
        <Card3D className="card-rsvp" delay={0}>
          <div className="card-icon">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="14" stroke="#10b981" strokeWidth="2" fill="none" />
              <path d="M10 16L14 20L22 12" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="card-label">Confirmed</div>
          <div className="card-value">{rsvpCount}</div>
          <div className="card-sublabel">RSVPs</div>
        </Card3D>

        {/* Total Guests - Top Right */}
        <Card3D className="card-guests" delay={0.2}>
          <div className="card-icon">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M16 18C19.866 18 23 14.866 23 11C23 7.134 19.866 4 16 4C12.134 4 9 7.134 9 11C9 14.866 12.134 18 16 18Z" stroke="#8b5cf6" strokeWidth="2" />
              <path d="M25 28C25 23.582 21.418 20 17 20H15C10.582 20 7 23.582 7 28" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
          <div className="card-label">Total Guests</div>
          <div className="card-value">{guestCount}</div>
          <div className="card-sublabel">Invited</div>
        </Card3D>

        {/* Timeline - Bottom Left */}
        <Card3D className="card-timeline" delay={0.4}>
          <div className="card-label">Timeline</div>
          <div className="timeline-steps">
            <div className="timeline-step completed">
              <div className="step-dot" />
              <span>Engaged</span>
            </div>
            <div className="timeline-step active">
              <div className="step-dot pulse" />
              <span>Planning</span>
            </div>
            <div className="timeline-step">
              <div className="step-dot" />
              <span>Big Day</span>
            </div>
          </div>
        </Card3D>

        {/* Vendors - Bottom Right */}
        <Card3D className="card-vendors" delay={0.6}>
          <div className="card-label">Vendors</div>
          <div className="vendor-grid">
            <div className="vendor-item confirmed">
              <span>🍰</span>
            </div>
            <div className="vendor-item confirmed">
              <span>📸</span>
            </div>
            <div className="vendor-item">
              <span>🎵</span>
            </div>
            <div className="vendor-item confirmed">
              <span>💐</span>
            </div>
          </div>
        </Card3D>
      </div>

      <style jsx>{`
        .elegant-hero-container {
          position: relative;
          width: 100%;
          height: 600px;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          background: linear-gradient(135deg, #FFF8F0 0%, #FFF0E5 50%, #FFE4D6 100%);
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

        /* Card grid - clean 2x2 layout */
        .hero-grid {
          position: relative;
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 2rem;
          max-width: 800px;
          padding: 2rem;
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

        /* Card styling - warm wedding colors */
        .card-icon {
          margin-bottom: 1rem;
        }

        .card-label {
          font-size: 0.75rem;
          font-weight: 500;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #A89080;
          margin-bottom: 0.5rem;
        }

        .card-value {
          font-size: 3rem;
          font-weight: 700;
          color: #8B7355;
          line-height: 1;
          margin-bottom: 0.25rem;
        }

        .card-sublabel {
          font-size: 0.875rem;
          color: #B5A79A;
        }

        /* Timeline steps */
        .timeline-steps {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          margin-top: 1rem;
        }

        .timeline-step {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .step-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background: #E5DDD5;
          position: relative;
        }

        .timeline-step.completed .step-dot {
          background: #10b981;
        }

        .timeline-step.active .step-dot {
          background: #8b5cf6;
        }

        .step-dot.pulse::after {
          content: '';
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          border: 2px solid #8b5cf6;
          animation: pulse 2s ease-out infinite;
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0;
            transform: scale(1.5);
          }
        }

        .timeline-step span {
          font-size: 0.875rem;
          color: #8B7355;
        }

        .timeline-step.completed span {
          text-decoration: line-through;
          opacity: 0.6;
        }

        .timeline-step.active span {
          font-weight: 600;
        }

        /* Vendor grid */
        .vendor-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 0.75rem;
          margin-top: 1rem;
        }

        .vendor-item {
          aspect-ratio: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(255, 255, 255, 0.3);
          border-radius: 12px;
          font-size: 1.5rem;
          position: relative;
          transition: transform 0.3s cubic-bezier(0.23, 1, 0.32, 1);
        }

        .vendor-item:hover {
          transform: scale(1.1);
        }

        .vendor-item.confirmed::after {
          content: '';
          position: absolute;
          top: -4px;
          right: -4px;
          width: 16px;
          height: 16px;
          background: #10b981;
          border-radius: 50%;
          border: 2px solid white;
        }

        /* Accessibility */
        @media (prefers-reduced-motion: reduce) {
          .petal,
          .wedding-card,
          .step-dot.pulse::after {
            animation: none;
          }

          .wedding-card {
            opacity: 1;
            transform: none;
          }
        }

        /* Responsive */
        @media (max-width: 768px) {
          .hero-grid {
            grid-template-columns: 1fr;
            gap: 1rem;
          }
        }
      `}</style>
    </div>
  );
}
