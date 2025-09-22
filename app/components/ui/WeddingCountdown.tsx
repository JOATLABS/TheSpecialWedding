'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/utils/cn';
import type { ThemeConfig as WeddingThemeConfig } from '@/types/wedding';

interface CountdownConfig {
  enabled: boolean;
  target_date?: string;
  display_style: 'elegant' | 'modern' | 'minimal' | 'bold';
  show_seconds: boolean;
  show_labels: boolean;
  custom_message?: string;
  position: 'hero' | 'header' | 'floating';
}

type ThemeConfig = WeddingThemeConfig & {
  primaryColor?: string;
  secondaryColor?: string;
  fontFamily?: string;
};

interface WeddingCountdownProps {
  weddingDate: string;
  countdownConfig?: CountdownConfig;
  themeConfig?: ThemeConfig;
  className?: string;
}

interface TimeLeft {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
}

export const WeddingCountdown: React.FC<WeddingCountdownProps> = ({
  weddingDate,
  countdownConfig,
  themeConfig,
  className
}) => {
  const [timeLeft, setTimeLeft] = useState<TimeLeft>({ days: 0, hours: 0, minutes: 0, seconds: 0 });
  const [isClient, setIsClient] = useState(false);

  // Don't render if countdown is not enabled
  if (!countdownConfig?.enabled) {
    return null;
  }

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    if (!isClient) return;

    const calculateTimeLeft = () => {
      const targetDate = countdownConfig.target_date || weddingDate;
      const difference = +new Date(targetDate) - +new Date();

      if (difference > 0) {
        setTimeLeft({
          days: Math.floor(difference / (1000 * 60 * 60 * 24)),
          hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
          minutes: Math.floor((difference / 1000 / 60) % 60),
          seconds: Math.floor((difference / 1000) % 60),
        });
      } else {
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
      }
    };

    calculateTimeLeft();
    const timer = setInterval(calculateTimeLeft, 1000);

    return () => clearInterval(timer);
  }, [weddingDate, countdownConfig.target_date, isClient]);

  if (!isClient) {
    // Return placeholder during SSR
    return (
      <div className={cn("flex justify-center", className)}>
        <div className="animate-pulse bg-gray-200 h-20 w-80 rounded-lg"></div>
      </div>
    );
  }

  const getStyleClasses = () => {
    switch (countdownConfig.display_style) {
      case 'elegant':
        return {
          container: 'bg-white/90 backdrop-blur-sm shadow-xl border border-gray-200/50 rounded-2xl p-6',
          timeContainer: 'flex gap-6 justify-center',
          timeBlock: 'text-center bg-gradient-to-b from-gray-50 to-white border border-gray-200 rounded-xl p-4 shadow-sm',
          number: 'text-3xl md:text-4xl font-bold text-gray-800 block',
          label: 'text-sm font-medium text-gray-600 uppercase tracking-wide mt-1'
        };
      case 'modern':
        return {
          container: 'bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white shadow-2xl',
          timeContainer: 'flex gap-4 justify-center',
          timeBlock: 'text-center bg-white/20 backdrop-blur-sm rounded-lg p-4',
          number: 'text-3xl md:text-4xl font-bold block',
          label: 'text-sm font-medium uppercase tracking-wide mt-1 opacity-90'
        };
      case 'minimal':
        return {
          container: 'bg-transparent',
          timeContainer: 'flex gap-8 justify-center text-gray-800',
          timeBlock: 'text-center',
          number: 'text-2xl md:text-3xl font-light block',
          label: 'text-xs uppercase tracking-wider mt-1 text-gray-600'
        };
      case 'bold':
        return {
          container: 'bg-gradient-to-r from-red-600 to-pink-600 rounded-3xl p-8 text-white shadow-2xl transform hover:scale-105 transition-transform',
          timeContainer: 'flex gap-6 justify-center',
          timeBlock: 'text-center',
          number: 'text-4xl md:text-6xl font-black block drop-shadow-lg',
          label: 'text-lg font-bold uppercase tracking-wide mt-2'
        };
      default:
        return {
          container: 'bg-white/90 backdrop-blur-sm shadow-lg rounded-lg p-4',
          timeContainer: 'flex gap-4 justify-center',
          timeBlock: 'text-center',
          number: 'text-2xl font-bold block',
          label: 'text-sm mt-1'
        };
    }
  };

  const styles = getStyleClasses();
  const timeUnits = [
    { value: timeLeft.days, label: 'Days' },
    { value: timeLeft.hours, label: 'Hours' },
    { value: timeLeft.minutes, label: 'Minutes' },
    ...(countdownConfig.show_seconds ? [{ value: timeLeft.seconds, label: 'Seconds' }] : [])
  ];

  return (
    <div className={cn("flex flex-col items-center", className)}>
      {countdownConfig.custom_message && (
        <p className="text-lg md:text-xl text-center mb-4 text-gray-700">
          {countdownConfig.custom_message}
        </p>
      )}

      <div className={styles.container}>
        <div className={styles.timeContainer}>
          {timeUnits.map((unit, index) => (
            <div key={unit.label} className={styles.timeBlock}>
              <span className={styles.number}>
                {unit.value.toString().padStart(2, '0')}
              </span>
              {countdownConfig.show_labels && (
                <span className={styles.label}>
                  {unit.label}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WeddingCountdown;