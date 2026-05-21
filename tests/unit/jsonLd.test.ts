import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

import { serializeJsonLd } from '../../app/seo/jsonLd';

describe('serializeJsonLd', () => {
  it('escapes script-breaking characters in untrusted JSON-LD strings', () => {
    const serialized = serializeJsonLd({
      '@context': 'https://schema.org',
      headline: '</script><script>alert(1)</script>',
      description: 'A & B > C',
    });

    assert(!serialized.includes('</script>'));
    assert(!serialized.includes('<script>'));
    assert(serialized.includes('\\u003c/script\\u003e'));
    assert(serialized.includes('\\u0026'));
    assert(serialized.includes('\\u003e'));
  });

  it('keeps public JSON-LD script tags on the shared serializer', () => {
    const publicJsonLdSources = [
      'app/page.tsx',
      'app/components/seo/BreadcrumbSchema.tsx',
      'app/resources/blog/[slug]/page.tsx',
      'app/resources/templates/page.tsx',
      'app/resources/faq/page.tsx',
      'app/vendors/page.tsx',
      'app/vendors/[id]/page.tsx',
    ];

    for (const sourcePath of publicJsonLdSources) {
      const source = readFileSync(sourcePath, 'utf8');
      assert.equal(
        source.includes('dangerouslySetInnerHTML={{ __html: JSON.stringify('),
        false,
        `${sourcePath} should serialize JSON-LD through serializeJsonLd`
      );
      assert.equal(
        source.includes('serializeJsonLd'),
        true,
        `${sourcePath} should import or call serializeJsonLd`
      );
    }
  });
});
