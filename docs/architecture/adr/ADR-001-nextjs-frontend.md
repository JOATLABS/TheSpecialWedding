# ADR-001: Use Next.js for Frontend Framework

## Status
Accepted

## Context
We need a modern frontend framework that can:
- Support both server-side rendering (SSR) and static site generation (SSG)
- Provide excellent SEO for public wedding pages
- Offer great developer experience with hot reloading
- Scale to handle multiple concurrent weddings
- Support progressive web app features

## Decision
We will use Next.js 15 with the App Router as our frontend framework.

## Consequences

### Positive
- **SEO Optimization**: SSR/SSG capabilities ensure wedding sites are search engine friendly
- **Performance**: Automatic code splitting, image optimization, and font optimization
- **Developer Experience**: TypeScript support, fast refresh, and comprehensive tooling
- **Routing**: File-based routing with the App Router simplifies navigation
- **API Routes**: Can create backend endpoints within Next.js if needed
- **Deployment**: Seamless deployment to Vercel with automatic optimizations
- **React 19 Support**: Latest React features including Server Components

### Negative
- **Learning Curve**: App Router is relatively new and requires understanding of Server Components
- **Vendor Lock-in**: Some optimizations work best on Vercel platform
- **Build Times**: Large applications can have longer build times
- **Complexity**: Server Components add complexity to data fetching patterns

### Neutral
- **Framework Size**: Larger than vanilla React but provides many built-in features
- **Opinionated Structure**: Enforces certain patterns which can be limiting or helpful

## Alternatives Considered
1. **Create React App**: Too basic, lacks SSR/SSG
2. **Gatsby**: Better for static sites, not ideal for dynamic content
3. **Remix**: Good alternative but smaller ecosystem
4. **Vite + React**: Would require additional SSR setup

## References
- [Next.js Documentation](https://nextjs.org/docs)
- [Next.js App Router](https://nextjs.org/docs/app)
- [React Server Components](https://react.dev/blog/2023/03/22/react-labs-what-we-have-been-working-on-march-2023#react-server-components)