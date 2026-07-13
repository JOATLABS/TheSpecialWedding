import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const source = (path: string) => readFileSync(path, 'utf8');

describe('Phase 1 planner operating-system message', () => {
  const homepage = source('app/page.tsx');
  const rootMetadata = source('app/layout.tsx');
  const featuresMetadata = source('app/features/layout.tsx');
  const featuresPage = source('app/features/page.tsx');
  const heroProof = source('app/components/landing-page/PhaseOneHeroProof.tsx');

  it('keeps the buyer and founder story planner-specific', () => {
    assert.match(homepage, /connected operating system built specifically for wedding planners/i);
    assert.match(homepage, /Founder perspective/);
    assert.match(homepage, /Emmanuel Akinwale/);
    assert.match(homepage, /The gaps between them are/);
    assert.doesNotMatch(homepage, /Phase 1 is not a feature-count story/);
    assert.doesNotMatch(featuresMetadata, /planners, couples, and vendors/i);
  });

  it('does not manufacture customer proof before the strategy calls for it', () => {
    assert.doesNotMatch(homepage, /testimonials?/i);
    assert.doesNotMatch(homepage, /saas\/public\/testimonials/);
  });

  it('keeps public metadata outcome-led and aligned to current pricing', () => {
    assert.match(rootMetadata, /connected operating system/i);
    assert.match(featuresMetadata, /connected wedding planner workspace/i);
    assert.doesNotMatch(rootMetadata, /featureCount/);
    assert.doesNotMatch(featuresMetadata, /\d+ tools/i);
    assert.match(rootMetadata, /lowPrice: '0'/);
    assert.match(rootMetadata, /highPrice: '399'/);
    assert.match(rootMetadata, /offerCount: 4/);
  });

  it('has a gated homepage entry point for the manually approved hero walkthrough', () => {
    assert.match(homepage, /HERO_DEMO_VIDEO/);
    assert.match(homepage, /<PhaseOneHeroProof demo=\{heroDemo\}/);
    assert.match(heroProof, /DemoVideoLauncher/);
    assert.match(heroProof, /Watch the planner workspace walkthrough/);
  });

  it('keeps the Features product-story CTA on the current page', () => {
    assert.match(featuresPage, /href="#showcase"/);
    assert.doesNotMatch(featuresPage, /href="\/#showcase"/);
    assert.match(featuresPage, /<section id="showcase"/);
  });
});
