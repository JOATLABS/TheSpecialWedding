# Frontend dependency checklist

The admin dashboard and marketing landing experience rely on UI libraries that must be present locally before starting the Next.js dev server.

## Required packages

- [`lucide-react`](https://www.npmjs.com/package/lucide-react) – icon set used across admin navigation and marketing components.
- [`tailwind-merge`](https://www.npmjs.com/package/tailwind-merge) – utility for merging Tailwind CSS class names when composing component variants.

## Installation

This repository uses `npm` and `package-lock.json` as the only supported frontend dependency workflow.
Install the dependencies with the workspace lockfile to ensure consistent versions:

```bash
npm ci
npm run deps:doctor
```

If the local tree is stale, partially installed, or missing expected binaries, reset it completely:

```bash
rm -rf node_modules
npm ci
npm run deps:doctor
```

If you intentionally changed frontend dependencies, use `npm install` and commit the updated `package-lock.json`.

After installation, verify that the frontend toolchain still resolves cleanly:

```bash
npm run lint
npm run type-check
npm run build
```
