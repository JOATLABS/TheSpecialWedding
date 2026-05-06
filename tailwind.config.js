/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class', // Use class-based dark mode (toggled via 'dark' class on html element)
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
        // Light/Dark mode colors
        'light-bg': '#F8FAFC',
        'dark-bg': '#0F172A',
        'light-text': '#1E293B',
        'dark-text': '#F1F5F9',
        // Primary colors for both modes
        'primary': {
          50: '#FFF5F5',
          100: '#FFE3E3',
          200: '#FFC7C7',
          300: '#FFA8A8',
          400: '#D4A5A5',
          500: '#C08080',
          600: '#A06060',
          700: '#804040',
          800: '#602020',
          900: '#401010',
        },
        // Secondary colors
        'secondary': {
          50: '#F0FDFA',
          100: '#CCFBF1',
          200: '#A8DADC',
          300: '#80C7C9',
          400: '#5FB4B6',
          500: '#3FA1A3',
          600: '#2E8082',
          700: '#1F6061',
          800: '#104040',
          900: '#082020',
        },
      },
      fontFamily: {
        'wedding': ['Playfair Display', 'serif'],
        'elegant': ['Cormorant Garamond', 'serif'],
        'heading': ['Playfair Display', 'Georgia', 'serif'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'parallax-slow': 'parallaxSlow 30s ease-in-out infinite',
        'parallax-medium': 'parallaxMedium 25s ease-in-out infinite',
        'parallax-fast': 'parallaxFast 20s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'flash': 'flash 1.5s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        flash: {
          '0%, 100%': { backgroundColor: 'transparent' },
          '20%': { backgroundColor: 'rgb(254 240 138)' },
          '60%': { backgroundColor: 'rgb(254 249 195)' },
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
        float: {
          '0%, 100%': { transform: 'translateY(0) scale(1)' },
          '50%': { transform: 'translateY(-20px) scale(1.02)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
