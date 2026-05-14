import { test, expect } from '@playwright/test';

// Pick a slug whose static `relatedTemplates` array is populated (see
// `app/resources/blog/data.tsx`). `how-to-price-wedding-planning-services`
// has been tagged with `couple_intake` + `vendor_performance_review`.
const ARTICLE_SLUG = 'how-to-price-wedding-planning-services';

test.use({
  baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
});

test.describe('Blog → free templates internal link surface', () => {
  test('renders the Related templates card with deep-anchor links', async ({ page }) => {
    await page.goto(`/resources/blog/${ARTICLE_SLUG}`);

    const card = page.getByTestId('blog-related-templates');
    await expect(card).toBeVisible();
    await expect(card).toContainText(/related free templates/i);

    const templateLinks = card.getByTestId('blog-related-template-link');
    await expect(templateLinks.first()).toBeVisible();

    // At least one link should deep-link into a template anchor.
    const anchorLink = card.locator('a[href*="/resources/templates#"]').first();
    await expect(anchorLink).toHaveCount(1);
  });

  test('clicking a related template link lands on the indexable templates page', async ({ page }) => {
    await page.goto(`/resources/blog/${ARTICLE_SLUG}`);

    const anchorLink = page
      .getByTestId('blog-related-templates')
      .locator('a[href*="/resources/templates#"]')
      .first();

    await anchorLink.click();
    await expect(page).toHaveURL(/\/resources\/templates#.+$/);
    await expect(page.getByRole('heading', { name: /Free wedding planner templates/i })).toBeVisible();
  });
});
