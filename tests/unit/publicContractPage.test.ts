import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import {
  canShowPublicContractSignControls,
  getPublicContractErrorState,
  isPublicContractAlreadySigned,
  resolveVendorContractAccessToken,
} from '../../app/vendor-contract/publicContractPageState';

const PUBLIC_PAGE_SOURCE = readFileSync(
  resolve(process.cwd(), 'app/vendor-contract/[id]/PublicContractPageClient.tsx'),
  'utf8'
);

describe('public vendor contract page state', () => {
  it('prefers the canonical path token over the legacy query token when both exist', () => {
    assert.equal(
      resolveVendorContractAccessToken('path-token', 'query-token'),
      'path-token'
    );
    assert.equal(resolveVendorContractAccessToken(null, 'query-token'), 'query-token');
  });

  it('maps replaced, expired, revoked, and missing links into explicit UI states', () => {
    assert.deepEqual(getPublicContractErrorState(410), {
      title: 'Contract Version Replaced',
      message: 'This contract version has been replaced. Please use the latest link sent by the planner.',
      hint: 'Please use the newest contract link sent by the wedding planner.',
      isReplacedVersion: true,
    });
    assert.equal(getPublicContractErrorState(403).isReplacedVersion, false);
    assert.match(getPublicContractErrorState(404).message, /Contract not found/);
  });

  it('hides sign controls for signed or replaced contracts', () => {
    assert.equal(isPublicContractAlreadySigned('signed'), true);
    assert.equal(isPublicContractAlreadySigned('completed'), true);
    assert.equal(isPublicContractAlreadySigned('sent'), false);
    assert.equal(canShowPublicContractSignControls(false, false), true);
    assert.equal(canShowPublicContractSignControls(true, false), false);
    assert.equal(canShowPublicContractSignControls(false, true), false);
  });

  it('keeps the shared preview renderer and canonical path-token calls in the page source', () => {
    assert.match(PUBLIC_PAGE_SOURCE, /VendorContractPreview/);
    assert.match(
      PUBLIC_PAGE_SOURCE,
      /vendor-contract\/public\/contracts\/\$\{contractId\}\/\$\{encodeURIComponent\(token\)\}/
    );
    assert.match(
      PUBLIC_PAGE_SOURCE,
      /vendor-contract\/public\/contracts\/\$\{contractId\}\/\$\{encodeURIComponent\(token\)\}\/sign/
    );
  });
});
