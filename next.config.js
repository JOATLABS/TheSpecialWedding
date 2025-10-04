const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '78885567ce761574f5914f46808cde6a.r2.cloudflarestorage.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'media.thespecialwedding.com',
        port: '',
        pathname: '/**',
      },
    ],
  },
  transpilePackages: ['@hello-pangea/dnd'],
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }

    const fallbackTinyInvariantPath = path.resolve(
      __dirname,
      'app/utils/tinyInvariantFallback.ts'
    );
    let hasWarnedAboutFallback = false;

    const resolveTinyInvariant = () => {
      const candidates = ['tiny-invariant', '@hello-pangea/dnd/node_modules/tiny-invariant'];

      for (const candidate of candidates) {
        try {
          return require.resolve(candidate);
        } catch (error) {
          if (error?.code !== 'MODULE_NOT_FOUND') {
            throw error;
          }
        }
      }

      if (!hasWarnedAboutFallback) {
        // eslint-disable-next-line no-console
        console.warn(
          'The "tiny-invariant" package is missing. Using the local fallback implementation. '
        );
        hasWarnedAboutFallback = true;
      }

      return fallbackTinyInvariantPath;
    };

    // Fix for @hello-pangea/dnd dependency issues
    config.resolve.alias = {
      ...config.resolve.alias,
      'tiny-invariant': resolveTinyInvariant(),
    };

    return config;
  },
}

module.exports = nextConfig
