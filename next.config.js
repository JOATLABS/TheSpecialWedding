/** @type {import('next').NextConfig} */
const path = require('path')
const { execFileSync } = require('child_process')

const FULL_GIT_COMMIT = /^[0-9a-f]{40}$/i

const resolveAppBuildCommit = () => {
  const environmentCommit = [
    process.env.NEXT_PUBLIC_APP_BUILD_COMMIT,
    process.env.VERCEL_GIT_COMMIT_SHA,
    process.env.CF_PAGES_COMMIT_SHA,
    process.env.GITHUB_SHA,
    process.env.SOURCE_VERSION,
  ].find((candidate) => FULL_GIT_COMMIT.test(candidate || ''))

  if (environmentCommit) return environmentCommit

  try {
    const checkoutCommit = execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: __dirname,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
    return FULL_GIT_COMMIT.test(checkoutCommit) ? checkoutCommit : 'unverified-build'
  } catch {
    return 'unverified-build'
  }
}

const appBuildCommit = resolveAppBuildCommit()

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

  env: {
    NEXT_PUBLIC_APP_BUILD_COMMIT: appBuildCommit,
  },

  images: {
    formats: ['image/avif', 'image/webp'],
    qualities: [75, 90],
    localPatterns: [
      {
        pathname: '/**',
        search: '',
      },
      {
        pathname: '/marketing/product-proof/**',
      },
    ],
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
