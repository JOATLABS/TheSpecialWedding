import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import robots from '../../app/robots';
import {
  PRIVATE_ADMIN_LOGIN_PATH,
  PUBLIC_LOGIN_PATH,
  PUBLIC_OG_IMAGE_PATH,
  ROBOTS_ALLOWED_PATHS,
  ROBOTS_DISALLOWED_PATHS,
  buildPublicOgImagePath,
} from '../../app/seo/crawlPolicy';

function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

function firstRobotsRule() {
  const rules = asArray(robots().rules);
  assert.equal(rules.length > 0, true, 'robots() should emit at least one rule');
  return rules[0];
}

function longestRobotsMatch(path: string) {
  const rule = firstRobotsRule();
  const matches = [
    ...asArray(rule.allow).map((prefix) => ({ type: 'allow' as const, prefix })),
    ...asArray(rule.disallow).map((prefix) => ({ type: 'disallow' as const, prefix })),
  ].filter(({ prefix }) => path.startsWith(prefix));

  return matches.sort((a, b) => b.prefix.length - a.prefix.length)[0];
}

describe('robots crawl policy', () => {
  it('keeps private app surfaces blocked while allowing the public OG image route', () => {
    const rule = firstRobotsRule();

    assert.deepEqual(asArray(rule.allow), [...ROBOTS_ALLOWED_PATHS]);
    assert.deepEqual(asArray(rule.disallow), [...ROBOTS_DISALLOWED_PATHS]);
    assert.equal(asArray(rule.allow).includes(PUBLIC_OG_IMAGE_PATH), true);
    assert.equal(asArray(rule.disallow).includes('/api/'), true);
  });

  it('allows public dynamic OG images more specifically than the API disallow', () => {
    const blogOgPath = buildPublicOgImagePath({
      type: 'blog',
      slug: 'how-to-price-wedding-planning-services',
    });
    const vendorOgPath = buildPublicOgImagePath({
      type: 'vendor',
      id: '507f1f77bcf86cd799439011', // pragma: allowlist secret - Mongo ObjectId fixture
    });

    assert.equal(longestRobotsMatch(blogOgPath)?.type, 'allow');
    assert.equal(longestRobotsMatch(vendorOgPath)?.type, 'allow');
    assert.equal(longestRobotsMatch('/api/v1/blog/articles?limit=50')?.type, 'disallow');
  });

  it('routes public marketing sign-in links through the noindex login handoff', () => {
    const publicSources = [
      'app/components/saas/SaasNav.tsx',
      'app/components/saas/PlannerAuthSection.tsx',
      'app/couple/login/page.tsx',
      'app/features/page.tsx',
      'app/forgot-password/page.tsx',
      'app/not-found.tsx',
      'app/page.tsx',
      'app/reset-password/ResetPasswordPageClient.tsx',
    ];

    for (const sourcePath of publicSources) {
      const source = readFileSync(sourcePath, 'utf8');
      assert.equal(
        source.includes(`href="${PRIVATE_ADMIN_LOGIN_PATH}"`),
        false,
        `${sourcePath} should not expose the robots-blocked admin login as a crawlable href`
      );
    }

    assert.equal(
      readFileSync('app/login/page.tsx', 'utf8').includes('index: false'),
      true,
      `${PUBLIC_LOGIN_PATH} must stay noindex because it exists only as a public auth handoff`
    );
  });

  it('builds blog and vendor metadata images from the robots-allowed OG route source', () => {
    const blogSource = readFileSync('app/resources/blog/[slug]/page.tsx', 'utf8');
    const vendorSource = readFileSync('app/vendors/[id]/layout.tsx', 'utf8');

    assert.equal(blogSource.includes('buildPublicOgImagePath'), true);
    assert.equal(blogSource.includes('buildPublicOgImageUrl'), true);
    assert.equal(vendorSource.includes('buildPublicOgImagePath'), true);
    assert.equal(blogSource.includes('/api/og?type=blog'), false);
    assert.equal(vendorSource.includes('/api/og?type=vendor'), false);
  });
});
