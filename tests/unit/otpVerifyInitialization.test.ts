import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it } from 'node:test';

const pageSource = readFileSync(
  join(process.cwd(), 'app/otp/verify/page.tsx'),
  'utf8',
);

describe('OTP verify page initialization', () => {
  it('requests the first verification code after exchanging a tokenized RSVP link', () => {
    const exchangeIndex = pageSource.indexOf('await exchangeGuestInviteToken(slug, token);');
    const requestIndex = pageSource.indexOf('await requestInitialOtpForToken(token);');
    const scrubIndex = pageSource.indexOf("window.history.replaceState({}, '', `/otp/verify?");

    assert.notEqual(exchangeIndex, -1, 'token exchange call should be present');
    assert.notEqual(requestIndex, -1, 'initial OTP request call should be present');
    assert.notEqual(scrubIndex, -1, 'token scrubbing should be present');
    assert.ok(
      exchangeIndex < requestIndex && requestIndex < scrubIndex,
      'the page should exchange the token, request the first OTP, then remove the token from the URL',
    );
  });

  it('does not claim a code was sent before the delivery attempt completes', () => {
    assert.match(pageSource, /Sending your verification code/);
    assert.match(pageSource, /We could not send a code automatically/);
    assert.doesNotMatch(pageSource, /A 6-digit code was sent/);
  });
});
