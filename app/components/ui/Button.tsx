// components/ui/Button.tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  const base = 'px-5 py-2 rounded-md font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-1';

  let style = '';
  switch (variant) {
    case 'secondary':
      style = 'border border-white/60 bg-white/70 text-wedding-navy hover:border-wedding-rose hover:text-wedding-rose focus:ring-wedding-rose/60';
      break;
    case 'danger':
      style = 'bg-red-500 text-white hover:bg-red-600 focus:ring-red-400/80';
      break;
    case 'primary':
    default:
      style = 'bg-wedding-rose text-white hover:bg-wedding-gold focus:ring-wedding-gold/70';
      break;
  }

  return <button {...props} className={`${base} ${style} ${className}`} />;
}
