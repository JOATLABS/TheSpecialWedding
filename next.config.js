/** @type {import('next').NextConfig} */
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
  buildRemotePattern(process.env.AD_MEDIA_DOMAIN),
  buildRemotePattern(process.env.BLOG_MEDIA_DOMAIN),
].filter(Boolean)

const nextConfig = {
  // Proxy API requests to backend
  // - Coolify (single container): proxies to localhost:8000
  // - Kubernetes (separate containers): proxies to backend K8s service
  async rewrites() {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

    // Skip rewrites if frontend calls the API directly via public domain
    if (apiBaseUrl.includes('api.thespecialwedding')) {
      return [];
    }

    // K8s: backend service is at http://backend.wedding-app.svc.cluster.local:8000
    // Coolify: backend is at http://localhost:8000 in same container
    const backendUrl = process.env.BACKEND_SERVICE_URL || 'http://localhost:8000';

    if (process.env.NODE_ENV === 'production') {
      return [
        {
          source: '/api/proxy/:path*',
          destination: `${backendUrl}/:path*`,
        },
      ];
    }

    return [];
  },

  images: {
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
