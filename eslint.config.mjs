import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

const config = [
  ...nextCoreWebVitals,
  {
    ignores: ['docs/**', '.agents/**', '.claude/**']
  },
  {
    files: ['**/*.{js,jsx,mjs,ts,tsx,mts,cts}'],
    rules: {
      '@next/next/no-img-element': 'off',
      '@next/next/no-html-link-for-pages': 'off',
      'react/no-unescaped-entities': 'off'
    }
  }
];

export default config;
