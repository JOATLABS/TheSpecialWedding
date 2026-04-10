import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com';

let ContractMarkdownRenderer: typeof import('../../app/components/contracts/ContractMarkdownRenderer').default;
let VendorContractPreview: typeof import('../../app/components/contracts/VendorContractPreview').default;
let applyContractPreviewPlaceholders: typeof import('../../app/components/contracts/VendorContractPreview').applyContractPreviewPlaceholders;
let sortVendorContractPreviewSections: typeof import('../../app/components/contracts/VendorContractPreview').sortVendorContractPreviewSections;

describe('vendor contract preview', () => {
  before(async () => {
    ({ default: ContractMarkdownRenderer } = await import('../../app/components/contracts/ContractMarkdownRenderer'));
    ({
      default: VendorContractPreview,
      applyContractPreviewPlaceholders,
      sortVendorContractPreviewSections,
    } = await import('../../app/components/contracts/VendorContractPreview'));
  });

  beforeEach(() => {
    mock.restoreAll();
  });

  afterEach(() => {
    mock.restoreAll();
  });

  after(() => {
    ContractMarkdownRenderer = undefined as unknown as typeof ContractMarkdownRenderer;
    VendorContractPreview = undefined as unknown as typeof VendorContractPreview;
    applyContractPreviewPlaceholders = undefined as unknown as typeof applyContractPreviewPlaceholders;
    sortVendorContractPreviewSections = undefined as unknown as typeof sortVendorContractPreviewSections;
  });

  it('sanitizes unsafe HTML while preserving markdown formatting', () => {
    const markup = renderToStaticMarkup(
      <ContractMarkdownRenderer content={'**Strong**<script>alert("x")</script>'} />
    );

    assert.match(markup, /<strong>Strong<\/strong>/);
    assert.doesNotMatch(markup, /<script>/);
    assert.doesNotMatch(markup, /alert\("x"\)/);
  });

  it('sorts sections without mutating the input array', () => {
    const sections = [
      { id: 'second', title: 'Second', content: 'B', order: 2 },
      { id: 'first', title: 'First', content: 'A', order: 1 },
    ];

    const sorted = sortVendorContractPreviewSections(sections);

    assert.deepEqual(
      sorted.map((section) => section.id),
      ['first', 'second']
    );
    assert.deepEqual(
      sections.map((section) => section.id),
      ['second', 'first']
    );
  });

  it('only applies placeholder substitution when preview values are supplied', () => {
    const raw = 'Hello {{vendor_name}}';

    assert.equal(applyContractPreviewPlaceholders(raw), raw);
    assert.equal(
      applyContractPreviewPlaceholders(raw, { '{{vendor_name}}': 'Vendor Co' }),
      'Hello Vendor Co'
    );
  });

  it('renders custom clauses through the shared preview component', () => {
    const markup = renderToStaticMarkup(
      <VendorContractPreview
        sections={[
          {
            id: 'scope',
            title: 'Scope',
            content: 'Work with **care** for {{vendor_name}}.',
            order: 2,
          },
          {
            id: 'intro',
            title: 'Introduction',
            content: 'Welcome',
            order: 1,
          },
        ]}
        customClauses={'Custom note for {{vendor_name}}.'}
        placeholderValues={{ '{{vendor_name}}': 'Vendor Co' }}
      />
    );

    assert.match(markup, /Introduction/);
    assert.match(markup, /Scope/);
    assert.match(markup, /Custom Clauses/);
    assert.match(markup, /Vendor Co/);
    assert.doesNotMatch(markup, /{{vendor_name}}/);
  });

  it('renders terms and cancellation blocks through the shared preview composition', () => {
    const markup = renderToStaticMarkup(
      <VendorContractPreview
        sections={[]}
        termsAndConditions={'Pay the **deposit** within 7 days.'}
        cancellationPolicy={'Cancellation requires **written notice**.'}
      />
    );

    assert.match(markup, /Terms &amp; Conditions/);
    assert.match(markup, /Cancellation Policy/);
    assert.match(markup, /deposit/);
    assert.match(markup, /written notice/);
  });

  it('does not apply planner-only placeholder substitution when no preview values are supplied', () => {
    const markup = renderToStaticMarkup(
      <VendorContractPreview
        sections={[
          {
            id: 'scope',
            title: 'Scope',
            content: 'Hello {{vendor_name}}',
            order: 0,
          },
        ]}
      />
    );

    assert.match(markup, /{{vendor_name}}/);
  });
});
