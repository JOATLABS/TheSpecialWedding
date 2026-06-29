/**
 * Homepage starter-pack lead-capture flow.
 *
 * Verifies the new HomepageTemplatesBand: clicking "Get all 9 templates"
 * opens the shared TemplateDownloadModal, the form posts to the marketing
 * lead endpoint with the starter-pack sentinel + homepage_band UTM, and
 * the success state with the Resend link renders.
 */
import { test, expect } from '@playwright/test';

test.use({
  baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
});

interface CapturedRequest {
  body: Record<string, unknown>;
}

test.describe('Homepage starter-pack lead capture', () => {
  test('submits starter-pack with homepage_band UTM and shows resend link', async ({
    page,
  }) => {
    const captured: CapturedRequest[] = [];

    // Mock the lead-capture endpoint so the test does not depend on the
    // real backend / Resend deliverability. We accept any host because
    // the API base URL is environment-driven.
    await page.route('**/public/marketing/template-download', async (route) => {
      const request = route.request();
      const raw = request.postData() ?? '{}';
      let body: Record<string, unknown> = {};
      try {
        body = JSON.parse(raw);
      } catch {
        body = {};
      }
      captured.push({ body });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'created',
          email_dispatched: true,
          message: 'Check your inbox — your starter pack is on its way.',
        }),
      });
    });

    await page.goto('/');

    const band = page.getByTestId('homepage-templates-band');
    await band.scrollIntoViewIfNeeded();
    await expect(band).toBeVisible();

    await page.getByTestId('homepage-band-cta').click();

    const modal = page.getByTestId('homepage-band-modal');
    await expect(modal).toBeVisible();

    await page.getByTestId('homepage-band-email').fill('visitor@example.com');
    await page.getByTestId('homepage-band-submit').click();

    // Success state with Resend link is the Batch 13 contract.
    await expect(page.getByTestId('homepage-band-success')).toBeVisible();
    await expect(page.getByTestId('homepage-band-resend')).toBeVisible();
    await expect(page.getByTestId('homepage-band-success-cta')).toHaveAttribute(
      'href',
      '/resources/demos#forms-canvas-demo',
    );

    // Network call body must include the starter-pack sentinel and the
    // homepage_band UTM forwarded by the band component.
    expect(captured.length).toBeGreaterThanOrEqual(1);
    const submitted = captured[0].body;
    expect(submitted.template_id).toBe('starter_pack');
    expect(submitted.email).toBe('visitor@example.com');
    expect(submitted.utm_source).toBe('homepage_band');
    expect(submitted.utm_medium).toBe('organic');
    expect(submitted.utm_campaign).toBe('starter_pack');
  });
});
