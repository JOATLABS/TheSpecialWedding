import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

const source = readFileSync(
  path.join(process.cwd(), 'remotion/DemoVideoComposition.tsx'),
  'utf8',
);
const rendererSource = readFileSync(
  path.join(process.cwd(), 'scripts/demo-videos/render-demo-video.ts'),
  'utf8',
);
const rootSource = readFileSync(
  path.join(process.cwd(), 'remotion/Root.tsx'),
  'utf8',
);

describe('demo video marketing composition safety', () => {
  it('keeps production scaffolding and review labels out of rendered media', () => {
    for (const forbidden of [
      'Website walkthrough',
      'Social cutdown',
      'Browser recording required',
      '1920x1080',
      '1080x1920',
      'DEMO PREVIEW',
      'proof',
    ]) {
      assert.equal(source.includes(forbidden), false, `composition still exposes ${forbidden}`);
    }
  });

  it('preserves the full product window and uses the full web canvas height', () => {
    assert.match(source, /<Video[\s\S]*?src=\{staticFile\(props\.rawVideoPath\)\}[\s\S]*?objectFit:\s*['"]contain['"]/);
    assert.doesNotMatch(source, /objectFit:\s*isVertical\s*\?\s*['"]contain['"]\s*:\s*['"]cover['"]/);
    assert.match(source, /data-product-window/);
    assert.match(source, /data-web-product-window/);
    assert.match(source, /data-web-product-window[\s\S]*?inset:\s*0/);
    assert.doesNotMatch(source, /WEB_CAPTION_BAND_HEIGHT/);
    assert.doesNotMatch(source, /data-caption-band/);
    assert.doesNotMatch(source, /activeCaption|captionSafeArea|props\.captions/);
    assert.doesNotMatch(source, /audience/);
    assert.doesNotMatch(source, /formatLabel/);
    assert.equal(
      source.match(/The Special Wedding/g)?.length,
      2,
      'branding should appear in the social story and outro, never over the website product frame',
    );
    assert.match(source, /data-web-product-window[\s\S]*?opacity:\s*storyOpacity/);
  });

  it('uses the portrait canvas for a pillar-native story instead of leaving a dead lower half', () => {
    assert.match(source, /data-social-story/);
    assert.match(source, /props\.phaseOnePillar/);
    assert.match(source, /props\.socialOutcome/);
    assert.match(source, /flexDirection:\s*['"]column['"]/);
    assert.match(source, /justifyContent:\s*['"]space-between['"]/);
    assert.match(source, /padding:\s*['"]100px 80px 140px['"]/);
    assert.match(source, /fontSize:\s*84/);
    assert.match(source, /minHeight:\s*400/);
    assert.match(source, /data-social-product-window[\s\S]*?boxSizing:\s*['"]border-box['"]/);
    assert.doesNotMatch(source, /['"]220px 0 1025px['"]/);
    assert.match(rendererSource, /phaseOnePillar:\s*demo\.phaseOnePillar/);
    assert.match(rendererSource, /socialOutcome:\s*demo\.socialOutcome/);
  });

  it('requires real social story copy and previews an approved social contract', () => {
    assert.match(source, /Social video renders require phaseOnePillar and socialOutcome/);
    assert.doesNotMatch(source, /\|\|\s*['"]Planner operating system['"]/);
    assert.doesNotMatch(source, /\|\|\s*['"]Keep the wedding connected/);
    assert.match(rootSource, /demoId:\s*['"]connection-over-tools-social['"]/);
    assert.match(rootSource, /phaseOnePillar:\s*['"]Connection Over Tools['"]/);
    assert.match(rootSource, /socialOutcome:\s*['"]Keep planner, couple, and guest context connected without exposing planner controls\.['"]/);
  });

  it('uses readable outro type and fully removes the product story behind the CTA', () => {
    assert.match(source, /const storyOpacity = 1 - outroBackdropOpacity;/);
    assert.match(source, /data-demo-outro[\s\S]*?opacity:\s*outroBackdropOpacity/);
    assert.match(source, /data-demo-outro-content[\s\S]*?opacity:\s*outroContentOpacity/);
    assert.doesNotMatch(source, /data-demo-outro[\s\S]*?opacity:\s*outroOpacity/);
    assert.match(source, /const outroBrandFontSize = isVertical \? 32 : 36;/);
    assert.match(source, /const outroHeadlineFontSize = isVertical \? 84 : 96;/);
    assert.match(source, /const outroSupportingFontSize = 44;/);
    assert.doesNotMatch(source, /fontFamily:\s*['"]Inter,/);
  });

  it('keeps the music bed looping under absolute-time ducking instead of loop-relative volume', () => {
    assert.match(source, /<Audio\s+src=\{staticFile\(props\.musicPath\)\}/);
    assert.match(source, /loop/);
    assert.match(source, /musicVolumeAtSeconds\(frame \/ fps, props\.narrationWindows \?\? \[\]\)/);
    assert.doesNotMatch(
      source,
      /volume=\{\s*\(/,
      'music volume must be computed from the composition frame, not a loop-relative callback',
    );
    assert.match(rendererSource, /readNarrationWindows/);
    assert.match(rendererSource, /no-music/);
  });

  it('renders an explicit narration track instead of silently discarding the approved script', () => {
    assert.match(source, /import\s*\{[^}]*Audio[^}]*Video[^}]*\}\s*from\s*['"]@remotion\/media['"]/);
    assert.match(source, /<Audio\s+src=\{staticFile\(props\.narrationPath\)\}/);
    assert.match(source, /<Video[\s\S]*?muted/);
  });

  it('ends with a real activation CTA rather than promising one only in capture notes', () => {
    assert.match(source, /const OUTRO_DURATION_SECONDS = 5/);
    assert.match(source, /data-demo-outro/);
    assert.match(source, /One planner-owned workspace\./);
    assert.match(source, /Start with one wedding\./);
  });
});
