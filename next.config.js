/** @type {import('next').NextConfig} */
const path = require('path')

const buildRemotePattern = (value, defaultProtocol = 'https') => {
  if (!value) return null

  const normalized = /^https?:\/\//i.test(value) ? value : `${defaultProtocol}://${value}`

  try {
    const url = new URL(normalized)
    return {
      protocol: url.protocol.replace(':', ''),
      hostname: url.hostname,
      port: url.port,
      pathname: '/**',
    }
  } catch {
    return null
  }
}

const remotePatterns = [
  buildRemotePattern(process.env.S3_ENDPOINT_URL),
  buildRemotePattern(process.env.MEDIA_DOMAIN),
  buildRemotePattern(process.env.GUEST_MEDIA_DOMAIN),
  buildRemotePattern(process.env.AD_MEDIA_DOMAIN),
  buildRemotePattern(process.env.BLOG_MEDIA_DOMAIN),
].filter(Boolean)

const nextConfig = {
  outputFileTracingRoot: path.join(__dirname),

  images: {
    formats: ['image/avif', 'image/webp'],
    qualities: [75, 90],
    remotePatterns,
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
