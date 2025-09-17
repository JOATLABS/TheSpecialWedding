'use client';

import React from 'react';
import { Badge } from './badge';

interface NotificationBadgeProps {
  count: number;
  className?: string;
  maxCount?: number;
  showZero?: boolean;
  pulse?: boolean;
}

export function NotificationBadge({
  count,
  className = '',
  maxCount = 99,
  showZero = false,
  pulse = true
}: NotificationBadgeProps) {
  // Don't show badge if count is 0 and showZero is false
  if (count === 0 && !showZero) {
    return null;
  }

  // Format count display (e.g., "99+" for counts over maxCount)
  const displayCount = count > maxCount ? `${maxCount}+` : count.toString();

  return (
    <Badge
      variant="notification"
      className={`
        ${pulse && count > 0 ? 'animate-pulse' : ''}
        min-w-[1.25rem] h-5 p-0 flex items-center justify-center
        text-[10px] sm:text-xs font-bold leading-none
        ${className}
      `}
    >
      {displayCount}
    </Badge>
  );
}

interface NotificationIconWithBadgeProps {
  icon: React.ReactNode;
  count: number;
  className?: string;
  iconClassName?: string;
  badgeClassName?: string;
  maxCount?: number;
  showZero?: boolean;
}

export function NotificationIconWithBadge({
  icon,
  count,
  className = '',
  iconClassName = '',
  badgeClassName = '',
  maxCount = 99,
  showZero = false
}: NotificationIconWithBadgeProps) {
  return (
    <div className={`relative inline-flex ${className}`}>
      <div className={iconClassName}>
        {icon}
      </div>
      {(count > 0 || showZero) && (
        <NotificationBadge
          count={count}
          maxCount={maxCount}
          showZero={showZero}
          className={`absolute -top-1 -right-1 ${badgeClassName}`}
        />
      )}
    </div>
  );
}