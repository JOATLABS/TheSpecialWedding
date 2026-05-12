import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

type NextRewrite = {
  source?: string;
};

type RewriteConfig = NextRewrite[] | {
  beforeFiles?: NextRewrite[];
  afterFiles?: NextRewrite[];
  fallback?: NextRewrite[];
};

type NextConfigModule = {
  default?: {
    rewrites?: () => Promise<RewriteConfig>;
  };
  rewrites?: () => Promise<RewriteConfig>;
};

function flattenRewrites(rewrites: RewriteConfig): NextRewrite[] {
  if (Array.isArray(rewrites)) {
    return rewrites;
  }

  return [
    ...(rewrites.beforeFiles ?? []),
    ...(rewrites.afterFiles ?? []),
    ...(rewrites.fallback ?? []),
  ];
}

test('Next config does not bake the runtime API proxy into build-time rewrites', async () => {
  const configModule = await import('../../next.config.js') as NextConfigModule;
  const nextConfig = configModule.default ?? configModule;
  const rewrites = nextConfig.rewrites ? flattenRewrites(await nextConfig.rewrites()) : [];

  assert.equal(
    rewrites.some((rewrite) => rewrite.source === '/api/proxy/:path*'),
    false,
  );
});

const routesManifestPath = join(process.cwd(), '.next', 'routes-manifest.json');

test(
  'built routes manifest does not include a /api/proxy rewrite when present',
  { skip: !existsSync(routesManifestPath) },
  () => {
    const manifest = JSON.parse(readFileSync(routesManifestPath, 'utf8')) as {
      rewrites?: {
        beforeFiles?: NextRewrite[];
        afterFiles?: NextRewrite[];
        fallback?: NextRewrite[];
      };
    };
    const rewrites = [
      ...(manifest.rewrites?.beforeFiles ?? []),
      ...(manifest.rewrites?.afterFiles ?? []),
      ...(manifest.rewrites?.fallback ?? []),
    ];

    assert.equal(
      rewrites.some((rewrite) => rewrite.source === '/api/proxy/:path*'),
      false,
    );
  },
);
