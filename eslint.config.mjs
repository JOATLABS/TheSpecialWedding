import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

const config = [
  ...nextCoreWebVitals,
  {
    ignores: [
      'docs/**',
      '.agents/**',
      '.claude/**',
      '.next/**',
      '.venv*/**',
      'testbed/.testbed/**',
    ]
  },
  {
    files: ['**/*.{js,jsx,mjs,ts,tsx,mts,cts}'],
    rules: {
      '@next/next/no-img-element': 'off',
      '@next/next/no-html-link-for-pages': 'off',
      // Keep classic hooks checks while the app migrates legacy effects toward React Compiler-safe patterns.
      'react-hooks/config': 'off',
      'react-hooks/error-boundaries': 'off',
      'react-hooks/gating': 'off',
      'react-hooks/globals': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/incompatible-library': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/set-state-in-render': 'off',
      'react-hooks/static-components': 'off',
      'react-hooks/unsupported-syntax': 'off',
      'react-hooks/use-memo': 'off',
      'react-hooks/void-use-memo': 'off',
      'react/no-unescaped-entities': 'off'
    }
  }
];

export default config;
