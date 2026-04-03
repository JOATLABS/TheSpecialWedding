'use client';

import React, { useEffect, useState } from 'react';

export default function IsometricPlatformHero() {
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const [particles] = useState(() => (
    Array.from({ length: 8 }, () => ({
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      animation: `particle ${3 + Math.random() * 2}s ease-in-out infinite ${Math.random() * 2}s`,
      transform: `translateZ(${Math.random() * 100}px)`,
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

  return (
    <div className="relative w-full h-full flex items-center justify-center perspective-1000">
      {/* 3D Scene Container */}
      <div
        className="relative w-full max-w-4xl h-[500px] transform-gpu"
        style={{
          transform: `rotateX(${-mouseY * 0.3}deg) rotateY(${mouseX * 0.3}deg)`,
          transition: 'transform 0.3s ease-out',
        }}
      >
        {/* Main Platform Base */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="isometric-container">
            {/* Guest Management Card */}
            <div
              className="isometric-card bg-gradient-to-br from-blue-500/90 to-blue-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(60px) translateX(-200px) translateY(-100px)',
                animation: 'float 3s ease-in-out infinite',
              }}
            >
              <div className="p-4 text-white">
                <div className="text-xs font-semibold mb-2 text-blue-100">GUEST MANAGEMENT</div>
                <div className="text-2xl font-bold mb-1">487</div>
                <div className="text-xs text-blue-200">Total Guests</div>
                <div className="mt-3 flex gap-2">
                  <div className="flex-1 bg-blue-400/30 rounded h-1.5 overflow-hidden">
                    <div className="bg-green-400 h-full w-3/4 animate-pulse"></div>
                  </div>
                </div>
                <div className="text-xs text-blue-200 mt-1">342 Confirmed</div>
              </div>
            </div>

            {/* RSVP Stats Card */}
            <div
              className="isometric-card bg-gradient-to-br from-purple-500/90 to-purple-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(40px) translateX(200px) translateY(-80px)',
                animation: 'float 3s ease-in-out infinite 0.5s',
              }}
            >
              <div className="p-4 text-white">
                <div className="text-xs font-semibold mb-2 text-purple-100">RSVP STATUS</div>
                <div className="flex items-baseline gap-1 mb-2">
                  <span className="text-2xl font-bold">87</span>
                  <span className="text-sm text-purple-200">%</span>
                </div>
                <div className="h-2 bg-purple-400/30 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-green-400 to-green-500 w-[87%] animate-pulse"></div>
                </div>
              </div>
            </div>

            {/* Timeline Card */}
            <div
              className="isometric-card bg-gradient-to-br from-emerald-500/90 to-emerald-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(50px) translateX(-180px) translateY(100px)',
                animation: 'float 3s ease-in-out infinite 1s',
              }}
            >
              <div className="p-4 text-white">
                <div className="text-xs font-semibold mb-2 text-emerald-100">NEXT MILESTONE</div>
                <div className="text-sm font-bold mb-1">Vendor Deadline</div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-emerald-400/30 rounded-lg flex items-center justify-center">
                    <span className="text-lg">📅</span>
                  </div>
                  <div className="text-xs text-emerald-200">3 days remaining</div>
                </div>
              </div>
            </div>

            {/* Vendor Integration Card */}
            <div
              className="isometric-card bg-gradient-to-br from-orange-500/90 to-orange-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(35px) translateX(180px) translateY(120px)',
                animation: 'float 3s ease-in-out infinite 1.5s',
              }}
            >
              <div className="p-4 text-white">
                <div className="text-xs font-semibold mb-2 text-orange-100">VENDORS</div>
                <div className="flex gap-1 mb-2">
                  {['🍰', '📸', '🎵', '💐'].map((emoji, i) => (
                    <div
                      key={i}
                      className="w-8 h-8 bg-orange-400/30 rounded-lg flex items-center justify-center"
                      style={{ animation: `pulse 2s ease-in-out infinite ${i * 0.2}s` }}
                    >
                      {emoji}
                    </div>
                  ))}
                </div>
                <div className="text-xs text-orange-200">12 Active</div>
              </div>
            </div>

            {/* Notifications Card */}
            <div
              className="isometric-card bg-gradient-to-br from-pink-500/90 to-pink-600/90 backdrop-blur-sm"
              style={{
                transform: 'translateZ(45px) translateX(0px) translateY(0px)',
                animation: 'float 3s ease-in-out infinite 0.75s',
              }}
            >
              <div className="p-4 text-white">
                <div className="text-xs font-semibold mb-2 text-pink-100">LIVE UPDATES</div>
                <div className="space-y-1.5">
                  <div className="text-xs bg-pink-400/20 rounded px-2 py-1 animate-slideIn">
                    New RSVP received
                  </div>
                  <div className="text-xs bg-pink-400/20 rounded px-2 py-1 animate-slideIn" style={{ animationDelay: '0.3s' }}>
                    Vendor confirmed
                  </div>
                </div>
              </div>
            </div>

            {/* Connecting Lines/Data Flow */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ transform: 'translateZ(20px)' }}>
              <defs>
                <linearGradient id="lineGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.6" />
                </linearGradient>
              </defs>
              {/* Animated connection lines */}
              <line x1="40%" y1="30%" x2="60%" y2="40%" stroke="url(#lineGradient1)" strokeWidth="2" strokeDasharray="5,5">
                <animate attributeName="stroke-dashoffset" from="0" to="10" dur="1s" repeatCount="indefinite" />
              </line>
              <line x1="35%" y1="65%" x2="50%" y2="50%" stroke="url(#lineGradient1)" strokeWidth="2" strokeDasharray="5,5">
                <animate attributeName="stroke-dashoffset" from="0" to="10" dur="1s" repeatCount="indefinite" />
              </line>
              <line x1="65%" y1="70%" x2="50%" y2="50%" stroke="url(#lineGradient1)" strokeWidth="2" strokeDasharray="5,5">
                <animate attributeName="stroke-dashoffset" from="0" to="10" dur="1s" repeatCount="indefinite" />
              </line>
            </svg>

            {/* Floating Data Particles */}
            {particles.map((particle, i) => (
              <div
                key={i}
                className="absolute w-2 h-2 bg-blue-400/60 rounded-full blur-sm"
                style={particle}
              />
            ))}
          </div>
        </div>

        {/* Glow Effect Behind Platform */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>
      </div>

      <style jsx>{`
        .perspective-1000 {
          perspective: 1000px;
        }

        .isometric-container {
          position: relative;
          width: 100%;
          height: 100%;
          transform-style: preserve-3d;
        }

        .isometric-card {
          position: absolute;
          border-radius: 12px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          transform-style: preserve-3d;
          transition: transform 0.3s ease-out;
        }

        .isometric-card:hover {
          transform: translateZ(80px) !important;
        }

        @keyframes float {
          0%, 100% {
            transform: translateY(0px);
          }
          50% {
            transform: translateY(-20px);
          }
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.8;
            transform: scale(1.05);
          }
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(-10px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        @keyframes particle {
          0%, 100% {
            opacity: 0;
            transform: translateY(0) translateZ(0);
          }
          50% {
            opacity: 1;
            transform: translateY(-100px) translateZ(50px);
          }
        }
      `}</style>
    </div>
  );
}
