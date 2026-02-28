import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';
import { twMerge } from 'tailwind-merge';

interface GlassButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

export function GlassButton({
  className,
  variant = 'primary',
  size = 'md',
  icon,
  children,
  ...props
}: GlassButtonProps) {
  const baseStyles = `
    relative overflow-hidden
    inline-flex items-center justify-center gap-2
    font-medium transition-all duration-300
    backdrop-blur-md border border-white/20
    shadow-[0_4px_16px_0_rgba(31,38,135,0.07)]
    disabled:opacity-50 disabled:cursor-not-allowed
  `;

  const variants = {
    primary: 'bg-blue-600/80 hover:bg-blue-600/90 text-white shadow-blue-500/20',
    secondary: 'bg-white/40 hover:bg-white/60 text-gray-800 hover:shadow-lg dark:bg-slate-700/40 dark:hover:bg-slate-700/60 dark:text-gray-200 dark:border-slate-600/30',
    danger: 'bg-red-500/80 hover:bg-red-500/90 text-white shadow-red-500/20',
    ghost: 'bg-transparent hover:bg-white/20 text-gray-700 hover:text-gray-900 border-transparent dark:text-gray-300 dark:hover:text-white dark:hover:bg-white/10',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs rounded-lg',
    md: 'px-4 py-2 text-sm rounded-xl',
    lg: 'px-6 py-3 text-base rounded-2xl',
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={twMerge(baseStyles, variants[variant], sizes[size], className)}
      {...props}
    >
      {/* Glossy reflection effect */}
      <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent" />

      {icon && <span className="w-4 h-4">{icon}</span>}
      {children}
    </motion.button>
  );
}
