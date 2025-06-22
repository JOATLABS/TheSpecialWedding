/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Wedding color palette
        'wedding-rose': '#D4A5A5',
        'wedding-sage': '#A8DADC',
        'wedding-ivory': '#F1F3F4',
        'wedding-gold': '#E9C46A',
        'wedding-navy': '#1D3557',
        'wedding-blush': '#F8E8E8',
      },
      fontFamily: {
        'wedding': ['Playfair Display', 'serif'],
        'elegant': ['Cormorant Garamond', 'serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'parallax-slow': 'parallaxSlow 30s ease-in-out infinite',
        'parallax-medium': 'parallaxMedium 25s ease-in-out infinite',
        'parallax-fast': 'parallaxFast 20s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        parallaxSlow: {
          '0%': { transform: 'scale(1.2) translateX(0%) translateY(0%)' },
          '25%': { transform: 'scale(1.2) translateX(-2%) translateY(-1%)' },
          '50%': { transform: 'scale(1.2) translateX(-1%) translateY(-2%)' },
          '75%': { transform: 'scale(1.2) translateX(1%) translateY(-1%)' },
          '100%': { transform: 'scale(1.2) translateX(0%) translateY(0%)' },
        },
        parallaxMedium: {
          '0%': { transform: 'scale(1.15) translateX(0%) translateY(0%)' },
          '33%': { transform: 'scale(1.15) translateX(1%) translateY(-1.5%)' },
          '66%': { transform: 'scale(1.15) translateX(-1.5%) translateY(1%)' },
          '100%': { transform: 'scale(1.15) translateX(0%) translateY(0%)' },
        },
        parallaxFast: {
          '0%': { transform: 'scale(1.1) translateX(0%) translateY(0%)' },
          '50%': { transform: 'scale(1.1) translateX(-1%) translateY(1%)' },
          '100%': { transform: 'scale(1.1) translateX(0%) translateY(0%)' },
        },
      },
    },
  },
  plugins: [],
}