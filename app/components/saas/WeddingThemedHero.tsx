'use client';

import React, { useEffect, useState } from 'react';

export default function WeddingThemedHero() {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [rsvpCount, setRsvpCount] = useState(0);
  const [guestCount, setGuestCount] = useState(0);
  const [confettiParticles] = useState(() => (
    Array.from({ length: 20 }, () => ({
      left: `${Math.random() * 100}%`,
      top: `${-10 + Math.random() * 20}%`,
      animationDelay: `${Math.random() * 3}s`,
      animationDuration: `${3 + Math.random() * 2}s`,
      icon: ['💍', '💐', '🎉', '✨', '💕', '🥂'][Math.floor(Math.random() * 6)],
    }))
  ));
  const [sparklePositions] = useState(() => (
    Array.from({ length: 6 }, (_, index) => ({
      left: `${20 + Math.random() * 60}%`,
      top: `${20 + Math.random() * 60}%`,
      animationDelay: `${index * 0.3}s`,
    }))
  ));

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth - 0.5) * 20;
      const y = (e.clientY / window.innerHeight - 0.5) * 20;
      setMouseX(x);
      setMouseY(y);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Animated counters on mount
  useEffect(() => {
    const rsvpTimer = setInterval(() => {
      setRsvpCount((prev) => {
        if (prev >= 342) {
          clearInterval(rsvpTimer);
          return 342;
        }
        return prev + 17;
      });
    }, 50);

    const guestTimer = setInterval(() => {
      setGuestCount((prev) => {
        if (prev >= 487) {
          clearInterval(guestTimer);
          return 487;
        }
        return prev + 24;
      });
    }, 50);

    return () => {
      clearInterval(rsvpTimer);
      clearInterval(guestTimer);
    };
  }, []);

  return (
    <div className="relative w-full h-full flex items-center justify-center perspective-1000">
      {/* Confetti particles - wedding celebration theme */}
      {confettiParticles.map((particle, i) => (
        <div
          key={`confetti-${i}`}
          className="absolute confetti"
          style={{
            left: particle.left,
            top: particle.top,
            animationDelay: particle.animationDelay,
            animationDuration: particle.animationDuration,
          }}
        >
          {particle.icon}
        </div>
      ))}

      {/* 3D Scene Container */}
      <div
        className="relative w-full max-w-5xl h-[600px] transform-gpu"
        style={{
          transform: `rotateX(${-mouseY * 0.3}deg) rotateY(${mouseX * 0.3}deg)`,
          transition: 'transform 0.3s ease-out',
        }}
      >
        {/* Main Platform Base */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="isometric-container">
            {/* Central Ring Exchange Animation */}
            <div
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
              style={{ transform: 'translateZ(80px)' }}
            >
              <div className="relative w-32 h-32 flex items-center justify-center">
                {/* Left ring */}
                <div className="absolute ring-left">
                  <div className="w-16 h-16 rounded-full border-4 border-pink-400 shadow-lg shadow-pink-500/50" />
                </div>
                {/* Right ring */}
                <div className="absolute ring-right">
                  <div className="w-16 h-16 rounded-full border-4 border-blue-400 shadow-lg shadow-blue-500/50" />
                </div>
                {/* Hearts explosion when rings meet */}
                <div className="absolute hearts-burst">
                  {[...Array(8)].map((_, i) => (
                    <div
                      key={i}
                      className="absolute heart"
                      style={{
                        transform: `rotate(${i * 45}deg) translateY(-40px)`,
                        animationDelay: `${i * 0.1}s`,
                      }}
                    >
                      ❤️
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Live RSVP Counter Card - Top Left */}
            <div
              className="isometric-card bg-gradient-to-br from-emerald-500/90 to-emerald-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(60px) translateX(-250px) translateY(-120px)',
                animation: 'cardEntrance 1s ease-out',
              }}
            >
              <div className="p-6 text-white">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-10 h-10 bg-emerald-400/30 rounded-full flex items-center justify-center pulse-ring">
                    <span className="text-2xl">✅</span>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-emerald-100">LIVE RSVPs</div>
                    <div className="text-sm text-emerald-200">Just now</div>
                  </div>
                </div>
                <div className="text-4xl font-bold mb-2">{rsvpCount}</div>
                <div className="flex items-center gap-1 text-emerald-200 text-sm">
                  <span className="inline-block w-2 h-2 bg-emerald-400 rounded-full animate-ping" />
                  Confirmed guests
                </div>
              </div>
            </div>

            {/* Guest Count with Celebration - Top Right */}
            <div
              className="isometric-card bg-gradient-to-br from-purple-500/90 to-purple-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(50px) translateX(250px) translateY(-100px)',
                animation: 'cardEntrance 1s ease-out 0.2s backwards',
              }}
            >
              <div className="p-6 text-white relative overflow-hidden">
                <div className="relative z-10">
                  <div className="text-xs font-semibold mb-2 text-purple-100">TOTAL GUESTS</div>
                  <div className="text-5xl font-bold mb-1">{guestCount}</div>
                  <div className="flex gap-1 mt-3">
                    {[1, 2, 3, 4].map((_, i) => (
                      <div
                        key={i}
                        className="w-8 h-8 bg-purple-400/30 rounded-lg flex items-center justify-center celebrate-icon"
                        style={{ animationDelay: `${i * 0.2}s` }}
                      >
                        🎊
                      </div>
                    ))}
                  </div>
                </div>
                {/* Floating sparkles */}
                <div className="absolute inset-0 sparkle-container">
                  {sparklePositions.map((sparkle, i) => (
                    <div
                      key={i}
                      className="absolute sparkle"
                      style={{
                        left: sparkle.left,
                        top: sparkle.top,
                        animationDelay: sparkle.animationDelay,
                      }}
                    >
                      ✨
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Wedding Timeline Progress - Bottom Left */}
            <div
              className="isometric-card bg-gradient-to-br from-pink-500/90 to-pink-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(45px) translateX(-220px) translateY(130px)',
                animation: 'cardEntrance 1s ease-out 0.4s backwards',
              }}
            >
              <div className="p-5 text-white">
                <div className="text-xs font-semibold mb-3 text-pink-100">WEDDING TIMELINE</div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 timeline-step completed">
                    <div className="w-6 h-6 bg-pink-400 rounded-full flex items-center justify-center text-xs">✓</div>
                    <span className="text-sm">Engagement</span>
                  </div>
                  <div className="flex items-center gap-2 timeline-step active">
                    <div className="w-6 h-6 bg-pink-300 rounded-full flex items-center justify-center pulse-dot">
                      <div className="w-2 h-2 bg-white rounded-full" />
                    </div>
                    <span className="text-sm font-semibold">Planning</span>
                  </div>
                  <div className="flex items-center gap-2 timeline-step upcoming">
                    <div className="w-6 h-6 bg-pink-400/30 rounded-full" />
                    <span className="text-sm opacity-60">Big Day</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Vendor Status - Bottom Right */}
            <div
              className="isometric-card bg-gradient-to-br from-amber-500/90 to-amber-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(55px) translateX(240px) translateY(140px)',
                animation: 'cardEntrance 1s ease-out 0.6s backwards',
              }}
            >
              <div className="p-5 text-white">
                <div className="text-xs font-semibold mb-3 text-amber-100">VENDOR STATUS</div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { icon: '🍰', status: 'confirmed' },
                    { icon: '📸', status: 'confirmed' },
                    { icon: '🎵', status: 'pending' },
                    { icon: '💐', status: 'confirmed' },
                  ].map((vendor, i) => (
                    <div
                      key={i}
                      className={`relative w-12 h-12 rounded-lg flex items-center justify-center text-xl vendor-badge ${
                        vendor.status === 'confirmed' ? 'bg-emerald-400/30' : 'bg-amber-400/30'
                      }`}
                      style={{ animationDelay: `${0.8 + i * 0.15}s` }}
                    >
                      {vendor.icon}
                      {vendor.status === 'confirmed' && (
                        <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full flex items-center justify-center text-xs checkmark-pop">
                          ✓
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Love meter - Center bottom */}
            <div
              className="isometric-card bg-gradient-to-br from-rose-500/90 to-rose-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(40px) translateX(0px) translateY(0px)',
                animation: 'cardEntrance 1s ease-out 0.8s backwards',
              }}
            >
              <div className="p-4 text-white text-center">
                <div className="text-xs font-semibold mb-2 text-rose-100">EXCITEMENT LEVEL</div>
                <div className="flex justify-center gap-1 mb-2">
                  {[...Array(5)].map((_, i) => (
                    <div
                      key={i}
                      className="heart-beat"
                      style={{ animationDelay: `${1 + i * 0.1}s` }}
                    >
                      ❤️
                    </div>
                  ))}
                </div>
                <div className="text-sm text-rose-200">Off the charts!</div>
              </div>
            </div>

            {/* Connecting celebration lines */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ transform: 'translateZ(20px)' }}>
              <defs>
                <linearGradient id="celebrationGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ec4899" stopOpacity="0.6" />
                  <stop offset="50%" stopColor="#8b5cf6" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.6" />
                </linearGradient>
              </defs>
              <line x1="35%" y1="35%" x2="50%" y2="50%" stroke="url(#celebrationGradient)" strokeWidth="2" strokeDasharray="5,5" className="celebration-line" />
              <line x1="65%" y1="35%" x2="50%" y2="50%" stroke="url(#celebrationGradient)" strokeWidth="2" strokeDasharray="5,5" className="celebration-line" style={{ animationDelay: '0.3s' }} />
              <line x1="35%" y1="65%" x2="50%" y2="50%" stroke="url(#celebrationGradient)" strokeWidth="2" strokeDasharray="5,5" className="celebration-line" style={{ animationDelay: '0.6s' }} />
              <line x1="65%" y1="65%" x2="50%" y2="50%" stroke="url(#celebrationGradient)" strokeWidth="2" strokeDasharray="5,5" className="celebration-line" style={{ animationDelay: '0.9s' }} />
            </svg>
          </div>
        </div>

        {/* Romantic glow effects */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-pink-500/20 rounded-full blur-3xl romantic-glow" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-purple-500/20 rounded-full blur-3xl romantic-glow" style={{ animationDelay: '1s' }} />
        </div>
      </div>

      <style jsx>{`
        .perspective-1000 {
          perspective: 1200px;
        }

        .isometric-container {
          position: relative;
          width: 100%;
          height: 100%;
          transform-style: preserve-3d;
        }

        .isometric-card {
          position: absolute;
          border-radius: 16px;
          box-shadow: 0 25px 70px rgba(0, 0, 0, 0.4);
          transform-style: preserve-3d;
          transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .isometric-card:hover {
          transform: translateZ(100px) scale(1.05) !important;
        }

        /* Confetti falling animation */
        @keyframes confettiFall {
          0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
          }
        }

        .confetti {
          font-size: 1.5rem;
          animation: confettiFall linear infinite;
          pointer-events: none;
        }

        /* Ring exchange animation */
        @keyframes ringMergeLeft {
          0%, 40% {
            transform: translateX(-50px) scale(0.8);
            opacity: 0;
          }
          60%, 100% {
            transform: translateX(0) scale(1);
            opacity: 1;
          }
        }

        @keyframes ringMergeRight {
          0%, 40% {
            transform: translateX(50px) scale(0.8);
            opacity: 0;
          }
          60%, 100% {
            transform: translateX(0) scale(1);
            opacity: 1;
          }
        }

        .ring-left {
          animation: ringMergeLeft 3s ease-in-out infinite;
        }

        .ring-right {
          animation: ringMergeRight 3s ease-in-out infinite;
        }

        /* Hearts burst */
        @keyframes heartBurst {
          0% {
            transform: rotate(var(--rotation, 0deg)) translateY(0) scale(0);
            opacity: 0;
          }
          50% {
            opacity: 1;
          }
          100% {
            transform: rotate(var(--rotation, 0deg)) translateY(-60px) scale(1.2);
            opacity: 0;
          }
        }

        .hearts-burst {
          pointer-events: none;
        }

        .heart {
          font-size: 1.2rem;
          animation: heartBurst 2s ease-out infinite;
        }

        /* Pulse ring effect */
        @keyframes pulseRing {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7);
          }
          50% {
            box-shadow: 0 0 0 10px rgba(52, 211, 153, 0);
          }
        }

        .pulse-ring {
          animation: pulseRing 2s ease-out infinite;
        }

        /* Celebrate icons */
        @keyframes celebrate {
          0%, 100% {
            transform: scale(1) rotate(0deg);
          }
          25% {
            transform: scale(1.2) rotate(-10deg);
          }
          75% {
            transform: scale(1.2) rotate(10deg);
          }
        }

        .celebrate-icon {
          animation: celebrate 1s ease-in-out infinite;
        }

        /* Sparkle effect */
        @keyframes sparkle {
          0%, 100% {
            opacity: 0;
            transform: scale(0);
          }
          50% {
            opacity: 1;
            transform: scale(1.3);
          }
        }

        .sparkle {
          animation: sparkle 2s ease-in-out infinite;
        }

        /* Timeline animations */
        .timeline-step.completed {
          animation: slideInLeft 0.6s ease-out;
        }

        .timeline-step.active {
          animation: slideInLeft 0.6s ease-out 0.2s backwards;
        }

        .timeline-step.upcoming {
          animation: slideInLeft 0.6s ease-out 0.4s backwards;
        }

        @keyframes slideInLeft {
          from {
            transform: translateX(-20px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }

        .pulse-dot {
          animation: pulseDot 1.5s ease-in-out infinite;
        }

        @keyframes pulseDot {
          0%, 100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.3);
          }
        }

        /* Vendor badges */
        .vendor-badge {
          animation: popIn 0.5s ease-out backwards;
        }

        @keyframes popIn {
          0% {
            transform: scale(0) rotate(-180deg);
            opacity: 0;
          }
          100% {
            transform: scale(1) rotate(0deg);
            opacity: 1;
          }
        }

        .checkmark-pop {
          animation: checkmarkPop 0.5s ease-out 0.3s backwards;
        }

        @keyframes checkmarkPop {
          0% {
            transform: scale(0);
          }
          50% {
            transform: scale(1.3);
          }
          100% {
            transform: scale(1);
          }
        }

        /* Heart beat */
        @keyframes heartBeat {
          0%, 100% {
            transform: scale(1);
          }
          10%, 30% {
            transform: scale(1.3);
          }
          20%, 40% {
            transform: scale(1.1);
          }
        }

        .heart-beat {
          animation: heartBeat 1.5s ease-in-out infinite;
        }

        /* Card entrance */
        @keyframes cardEntrance {
          from {
            transform: translateY(50px) scale(0.8);
            opacity: 0;
          }
          to {
            transform: translateY(0) scale(1);
            opacity: 1;
          }
        }

        /* Celebration line */
        @keyframes celebrationLine {
          0% {
            stroke-dashoffset: 10;
            opacity: 0.3;
          }
          100% {
            stroke-dashoffset: 0;
            opacity: 1;
          }
        }

        .celebration-line {
          animation: celebrationLine 1.5s ease-out infinite;
        }

        /* Romantic glow */
        @keyframes romanticGlow {
          0%, 100% {
            opacity: 0.3;
            transform: translate(-50%, -50%) scale(1);
          }
          50% {
            opacity: 0.6;
            transform: translate(-50%, -50%) scale(1.1);
          }
        }

        .romantic-glow {
          animation: romanticGlow 4s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
