'use client';

/**
 * GlassCard Component
 *
 * An animated glass-morphism card component using Framer Motion.
 * Supports multiple visual variants with smooth entrance animations.
 *
 * Note on Framer Motion:
 * Framer Motion is kept in the main bundle (not lazy-loaded) because:
 * - It's relatively lightweight (~80-100KB gzipped)
 * - Used across multiple components and pages
 * - Provides critical UI animations for interactive feedback
 * - Splitting would create unnecessary code complexity
 *
 * See LAZY_LOADING_OPTIMIZATION.md for more details
 */

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface GlassCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'hover-lift' | 'interactive';
}

export function GlassCard({
  children,
  className,
  variant = 'default',
  ...props
}: GlassCardProps) {
  const baseStyles = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl border border-white/50 dark:border-slate-700/50 shadow-sm rounded-2xl transition-all duration-300 relative overflow-hidden";

  const variants = {
    default: "",
    'hover-lift': "hover:shadow-xl hover:-translate-y-1 hover:border-white/80 dark:hover:border-slate-600",
    interactive: "cursor-pointer hover:bg-white/80 dark:hover:bg-slate-800/80 active:scale-[0.98]"
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(baseStyles, variants[variant], className)}
      {...props}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      {children}
    </motion.div>
  );
}
