# Frontend dependency checklist

The admin dashboard and marketing landing experience rely on UI libraries that must be present locally before starting the Next.js dev server.

## Required packages

- [`lucide-react`](https://www.npmjs.com/package/lucide-react) – icon set used across admin navigation and marketing components.
- [`tailwind-merge`](https://www.npmjs.com/package/tailwind-merge) – utility for merging Tailwind CSS class names when composing component variants.

## Installation

Install the dependencies with the workspace lockfile to ensure consistent versions:

```bash
npm ci
```

If the modules are missing in an existing clone, reinstall them explicitly:

```bash
npm install lucide-react tailwind-merge
```

After installation, verify that Next.js can load the optimized image pipeline without reporting missing packages:

```bash
npm run lint
npm run type-check
```
