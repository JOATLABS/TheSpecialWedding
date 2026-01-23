// components/ui/Button.tsx
import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'default' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'default', className = '', isLoading = false, disabled, children, ...props }, ref) => {
    const base = 'rounded-md font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed';

    // Size styles
    let sizeStyle = '';
    switch (size) {
      case 'sm':
        sizeStyle = 'px-3 py-1.5 text-sm';
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

    // Variant styles
    let variantStyle = '';
    switch (variant) {
      case 'secondary':
        variantStyle = 'border border-white/60 bg-white/70 text-wedding-navy hover:border-wedding-rose hover:text-wedding-rose focus:ring-wedding-rose/60';
        break;
      case 'danger':
        variantStyle = 'bg-red-500 text-white hover:bg-red-600 focus:ring-red-400/80';
        break;
      case 'outline':
        variantStyle = 'border border-gray-300 dark:border-slate-600 bg-transparent text-gray-700 dark:text-slate-200 hover:bg-gray-50 dark:hover:bg-slate-700 focus:ring-gray-400/80';
        break;
      case 'ghost':
        variantStyle = 'bg-transparent text-gray-700 dark:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-700 focus:ring-gray-400/80';
        break;
      case 'default':
        variantStyle = 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500';
        break;
      case 'primary':
      default:
        variantStyle = 'bg-wedding-rose text-white hover:bg-wedding-gold focus:ring-wedding-gold/70';
        break;
    }

    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-busy={isLoading}
        className={`${base} ${sizeStyle} ${variantStyle} ${className}`}
        {...props}
      >
        {isLoading && (
          <Loader2 className={`animate-spin ${size === 'icon' ? '' : 'mr-2 h-4 w-4'}`} size={16} />
        )}
        {(!isLoading || size !== 'icon') && children}
      </button>
    );
  }
);

Button.displayName = 'Button';
