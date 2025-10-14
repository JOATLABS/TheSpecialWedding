// components/ui/Badge.tsx
import React from 'react';

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline';
}

export function Badge({ variant = 'default', className = '', children, ...props }: BadgeProps) {
  const base = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors';

  let style = '';
  switch (variant) {
    case 'secondary':
      style = 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100';
      break;
    case 'destructive':
      style = 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100';
      break;
    case 'outline':
      style = 'border border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300';
      break;
    case 'default':
    default:
      style = 'bg-wedding-rose text-white';
      break;
  }

  return (
    <div {...props} className={`${base} ${style} ${className}`}>
      {children}
    </div>
  );
}
