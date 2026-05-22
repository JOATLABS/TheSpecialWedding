import { test, expect } from '@playwright/test';

test.use({
  baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
});

test.describe('Templates discovery surfaces', () => {
  test('SaasNav keeps templates inside Resources instead of a separate top-level link', async ({ page }) => {
    await page.goto('/');

    const header = page.locator('header');
    await expect(header.getByRole('link', { name: 'Free templates' })).toHaveCount(0);

    await header.getByRole('link', { name: 'Resources' }).click();
    await expect(page).toHaveURL(/\/resources\/blog$/);
  });

  test('mobile menu also omits a separate Free templates item', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/resources/templates');

    const header = page.locator('header');
    await expect(header.getByRole('link', { name: 'Free templates' })).toHaveCount(0);

    await header.getByRole('button', { name: 'Toggle menu' }).click();
    await expect(header.getByRole('link', { name: 'Resources' })).toBeVisible();
    await expect(header.getByRole('link', { name: 'Free templates' })).toHaveCount(0);
  });

  test('Resources hub renders templates as a first-class tab', async ({ page }) => {
    await page.goto('/resources/blog');

    await page.getByRole('link', { name: 'Templates', exact: true }).click();

    await expect(page).toHaveURL(/\/resources\/templates$/);
    await expect(page.getByRole('heading', { name: /Templates wedding planners can use today/i })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Download as PDF' }).first()).toBeVisible();
  });

  test('query-param templates URL activates the Resources templates tab', async ({ page }) => {
    await page.goto('/resources?tab=templates');

    await expect(page).toHaveURL(/\/resources\/templates$/);
    await expect(page.getByRole('heading', { name: /Templates wedding planners can use today/i })).toBeVisible();
  });

  test('templates URL is the stable indexable catalog page', async ({ page }) => {
    await page.goto('/resources/templates#order_of_events');

    await expect(page).toHaveURL(/\/resources\/templates#order_of_events$/);
    await expect(page.getByRole('heading', { name: /Templates wedding planners can use today/i })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Download as PDF' }).first()).toBeVisible();

    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://thespecialwedding.io/resources/templates',
    );
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
      'content',
      /index, follow/i,
    );

    const schemaText = await page.locator('script[type="application/ld+json"]').allTextContents();
    expect(schemaText.join('\n')).toContain(
      'https://thespecialwedding.io/resources/templates#template-list',
    );
    expect(schemaText.join('\n')).toContain(
      'https://thespecialwedding.io/resources/templates#order_of_events',
    );
  });
});
