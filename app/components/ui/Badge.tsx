// components/ui/badge.tsx
import React from 'react';

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'danger' | 'outline';

type BadgeProps = {
  variant?: BadgeVariant;
  className?: string;
  children: React.ReactNode;
};

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-primary-100 text-primary-800 border-primary-200',
  secondary: 'bg-secondary-100 text-secondary-700 border-secondary-200',
  success: 'bg-green-100 text-green-800 border-green-200',
  warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  danger: 'bg-red-100 text-red-800 border-red-200',
  outline: 'bg-transparent text-slate-700 border-slate-300',
};

export function Badge({ variant = 'default', className = '', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
