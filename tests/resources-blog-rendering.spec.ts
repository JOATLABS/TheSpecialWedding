import { test, expect } from '@playwright/test';

const ARTICLE_SLUG = 'how-to-price-wedding-planning-services';
const ARTICLE_TITLE = 'How to Price Your Wedding Planning Services in 2026';
const ARTICLE_BODY = "Let's be direct: most wedding planners underprice their services.";

test.use({
  baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
});

test.describe('Resources blog rendering', () => {
  test('blog cards navigate to canonical article URLs with rendered content', async ({ page }) => {
    await page.goto('/resources');

    await page.getByRole('link', { name: new RegExp(ARTICLE_TITLE, 'i') }).first().click();

    await expect(page).toHaveURL(new RegExp(`/resources/blog/${ARTICLE_SLUG}$`));
    const directArticle = page.locator('article').first();
    await expect(page.getByRole('heading', { level: 1, name: ARTICLE_TITLE })).toBeVisible();
    await expect(directArticle).toContainText(ARTICLE_BODY);
    await expect(directArticle).not.toContainText('<p>');
    await expect(directArticle).not.toContainText('<h3>');
  });
});
