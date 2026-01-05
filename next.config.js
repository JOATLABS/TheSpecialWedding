/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API requests to backend in Coolify single-container deployment
  // The backend runs on port 8000 inside the container
  async rewrites() {
    // In production (Coolify), proxy to localhost:8000 inside container
    // In development, NEXT_PUBLIC_API_BASE_URL handles direct requests
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

    // Only enable rewrites for production single-container deployment
    if (process.env.NODE_ENV === 'production' && !apiBaseUrl.includes('api.thespecialwedding')) {
      return [
        {
          source: '/api/proxy/:path*',
          destination: 'http://localhost:8000/:path*',
        },
      ];
    }

    return [];
  },

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
        hostname: process.env.MEDIA_DOMAIN || '',
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
