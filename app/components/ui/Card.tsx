// components/ui/card.tsx
import React from 'react';

type CardProps = {
  className?: string;
  children: React.ReactNode;
};

// Main Card container with glassmorphism and fade-in animation
export function Card({ className = '', children }: CardProps) {
  return (
    <div
      className={
        `bg-white dark:bg-gray-800 bg-opacity-60 dark:bg-opacity-60 backdrop-blur-lg rounded-2xl shadow-lg p-6 space-y-4 animate-fade-in ${className}`
      }
    >
      {children}
    </div>
  );
}

// Header wrapper (for title, subtitle, etc.)
export function CardHeader({ className = '', children }: CardProps) {
  return (
    <div className={`mb-4 ${className}`}>{children}</div>
  );
}

// Title styling, uses your elegant font and wedding navy color
export function CardTitle({ className = '', children }: CardProps) {
  return (
    <h2
      className={`text-2xl font-elegant text-wedding-navy dark:text-gray-100 ${className}`}
    >
      {children}
    </h2>
  );
}

// Content area inside the card
export function CardContent({ className = '', children }: CardProps) {
  return <div className={className}>{children}</div>;
}
