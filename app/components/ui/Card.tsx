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
        `bg-white dark:bg-slate-800 bg-opacity-60 dark:bg-opacity-80 backdrop-blur-lg rounded-2xl shadow-lg p-6 space-y-4 animate-fade-in ${className}`
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
      className={`text-2xl font-elegant text-wedding-navy dark:text-white ${className}`}
    >
      {children}
    </h2>
  );
}

// Content area inside the card
export function CardContent({ className = '', children }: CardProps) {
  return <div className={className}>{children}</div>;
}

// Description text in card header
export function CardDescription({ className = '', children }: CardProps) {
  return (
    <p className={`text-sm text-gray-600 dark:text-gray-400 ${className}`}>
      {children}
    </p>
  );
}

// Footer area for actions/buttons
export function CardFooter({ className = '', children }: CardProps) {
  return (
    <div className={`mt-4 flex items-center gap-2 ${className}`}>
      {children}
    </div>
  );
}
