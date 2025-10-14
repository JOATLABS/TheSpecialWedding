// components/ui/Button.tsx
import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'outline' | 'default' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export function Button({ variant = 'primary', size = 'default', className = '', children, ...props }: ButtonProps) {
  const base = 'rounded-md font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed';

  let sizeStyle = '';
  switch (size) {
    case 'sm':
      sizeStyle = 'px-3 py-1 text-sm';
      break;
    case 'lg':
      sizeStyle = 'px-6 py-3 text-lg';
      break;
    case 'icon':
      sizeStyle = 'p-2';
      break;
    case 'default':
    default:
      sizeStyle = 'px-5 py-2';
      break;
  }

  let variantStyle = '';
  switch (variant) {
    case 'secondary':
      variantStyle = 'border border-white/60 bg-white/70 text-wedding-navy hover:border-wedding-rose hover:text-wedding-rose focus:ring-wedding-rose/60';
      break;
    case 'danger':
      variantStyle = 'bg-red-500 text-white hover:bg-red-600 focus:ring-red-400/80';
      break;
    case 'outline':
      variantStyle = 'border border-gray-300 bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-400/60 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800';
      break;
    case 'ghost':
      variantStyle = 'bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-400/60 dark:text-gray-300 dark:hover:bg-gray-800';
      break;
    case 'default':
    case 'primary':
    default:
      variantStyle = 'bg-wedding-rose text-white hover:bg-wedding-gold focus:ring-wedding-gold/70';
      break;
  }

  return <button {...props} className={`${base} ${sizeStyle} ${variantStyle} ${className}`}>{children}</button>;
}
