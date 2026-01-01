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

  // Configure build behavior
  staticPageGenerationTimeout: 180,

  // Empty turbopack config to acknowledge we're using webpack config with Turbopack
  turbopack: {},

  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }

    try {
      require.resolve('tiny-invariant');
    } catch (error) {
      if (error?.code === 'MODULE_NOT_FOUND') {
        throw new Error(
          'Missing required dependency "tiny-invariant". Run "npm install" to ensure all packages are installed before starting Next.js.'
        );
      }

      throw error;
    }

    return config;
  },
}

module.exports = nextConfig
