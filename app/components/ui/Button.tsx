// components/ui/Button.tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'danger';
}
export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  const base = 'px-5 py-2 rounded-md font-semibold transition';
  const style =
    variant === 'primary'
      ? 'bg-wedding-rose text-white hover:bg-wedding-gold'
      : 'bg-red-500 text-white hover:bg-red-600';

  return <button {...props} className={`${base} ${style} ${className}`} />;
}
