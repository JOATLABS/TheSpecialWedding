import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { getSeatingAiErrorMessage } from '@/admin/seating/aiErrorMessage';

describe('getSeatingAiErrorMessage', () => {
  it('uses the backend detail message when detail is a structured object', () => {
    assert.equal(
      getSeatingAiErrorMessage({
        detail: {
          error: 'ai_not_configured',
          message: 'AI service is not configured. Please contact the administrator.',
          hint: 'GEMINI_API_KEY environment variable may be missing.',
        },
      }),
      'AI service is not configured. Please contact the administrator.'
    );
  });

  it('uses string detail responses from FastAPI', () => {
    assert.equal(
      getSeatingAiErrorMessage({ detail: 'Guests and tables are required for optimization' }),
      'Guests and tables are required for optimization'
    );
  });

  it('falls back to the nested error code when no friendly message exists', () => {
    assert.equal(
      getSeatingAiErrorMessage({ detail: { error: 'insufficient_credits' } }),
      'insufficient_credits'
    );
  });

  it('uses normal Error messages for thrown client-side failures', () => {
    assert.equal(
      getSeatingAiErrorMessage(new Error('Network request failed')),
      'Network request failed'
    );
  });

  it('uses the default fallback for empty or unknown payloads', () => {
    assert.equal(getSeatingAiErrorMessage({ detail: {} }), 'Failed to get AI suggestions');
    assert.equal(getSeatingAiErrorMessage(null), 'Failed to get AI suggestions');
  });
});
