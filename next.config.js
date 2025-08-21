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
    
    // Fix for @hello-pangea/dnd dependency issues
    config.resolve.alias = {
      ...config.resolve.alias,
      'tiny-invariant': require.resolve('tiny-invariant'),
    };
    
    return config;
  },
}

module.exports = nextConfig