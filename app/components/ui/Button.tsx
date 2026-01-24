// components/ui/Button.tsx
import React from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'default' | 'secondary' | 'danger' | 'outline' | 'ghost';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'default', className = '', isLoading = false, disabled, children, ...props }, ref) => {
    const base = 'rounded-md font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-1 flex items-center justify-center';

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
    const disabledStyle = isDisabled ? 'opacity-50 cursor-not-allowed' : '';
    const isIcon = size === 'icon';
    // If it's an icon button and it's loading, hide the icon (children) so we just show the spinner.
    // Otherwise (text button), we show spinner next to text.
    const showChildren = !(isLoading && isIcon);

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={isLoading}
        className={`${base} ${sizeStyle} ${variantStyle} ${disabledStyle} ${className}`}
        {...props}
      >
        {isLoading && <Loader2 className={`h-4 w-4 animate-spin ${showChildren && children ? 'mr-2' : ''}`} />}
        {showChildren && children}
      </button>
    );
  }
);

Button.displayName = "Button";
