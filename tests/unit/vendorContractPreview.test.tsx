import { after, afterEach, before, beforeEach, describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { cleanup, render } from '@testing-library/react';

import { installDom } from './testDom';

let ContractMarkdownRenderer: typeof import('../../app/components/contracts/ContractMarkdownRenderer').default;
let VendorContractPreview: typeof import('../../app/components/contracts/VendorContractPreview').default;
let applyContractPreviewPlaceholders: typeof import('../../app/components/contracts/VendorContractPreview').applyContractPreviewPlaceholders;
let sortVendorContractPreviewSections: typeof import('../../app/components/contracts/VendorContractPreview').sortVendorContractPreviewSections;
let domHandle: ReturnType<typeof installDom> | null = null;

describe('vendor contract preview', () => {
  before(async () => {
    domHandle = installDom();
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
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    ContractMarkdownRenderer = undefined as unknown as typeof ContractMarkdownRenderer;
    VendorContractPreview = undefined as unknown as typeof VendorContractPreview;
    applyContractPreviewPlaceholders = undefined as unknown as typeof applyContractPreviewPlaceholders;
    sortVendorContractPreviewSections = undefined as unknown as typeof sortVendorContractPreviewSections;
  });

  it('sanitizes unsafe HTML while preserving markdown formatting', () => {
    const view = render(<ContractMarkdownRenderer content={'**Strong**<script>alert("x")</script>'} />);

    const strong = view.getByText('Strong');
    assert.equal(strong.tagName, 'STRONG');
    assert.equal(document.querySelector('script'), null);
    assert.equal(document.body.textContent?.includes('alert("x")'), false);
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

  it('renders sections and document blocks in stable preview order', () => {
    const view = render(
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
        termsAndConditions={'Pay the **deposit** within 7 days.'}
        cancellationPolicy={'Cancellation requires **written notice**.'}
        customClauses={'Custom note for {{vendor_name}}.'}
        placeholderValues={{ '{{vendor_name}}': 'Vendor Co' }}
      />
    );

    const headings = view.getAllByRole('heading', { level: 3 }).map((node) => node.textContent);
    assert.deepEqual(headings, [
      'Introduction',
      'Scope',
      'Terms & Conditions',
      'Cancellation Policy',
      'Custom Clauses',
    ]);
    assert.match(document.body.textContent || '', /Vendor Co/);
    assert.doesNotMatch(document.body.textContent || '', /{{vendor_name}}/);
  });

  it('does not apply planner-only placeholder substitution without preview values', () => {
    const view = render(
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

    view.getByText(/Hello {{vendor_name}}/);
  });
});
