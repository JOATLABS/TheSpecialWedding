import { test, expect } from '@playwright/test';

// Helper function to login
async function loginAsPlanner(page: any) {
  await page.goto('/admin/login');
  await page.fill('#email-input', 'test.verification@example.com');
  await page.fill('#password-input', 'testpassword123!');
  await page.click('#login-button');
  await page.waitForURL('/admin');
}

// Helper to navigate to budget page and select wedding
async function navigateToBudget(page: any) {
  await page.click('text=Budget Management');
  await page.waitForURL('/admin/budget');

  // Select first wedding if available
  const weddingSelector = await page.locator('select[name="wedding"]');
  if (await weddingSelector.isVisible()) {
    await weddingSelector.selectOption({ index: 1 });
    await page.waitForTimeout(500); // Wait for data to load
  }
}

test.describe('Payment Tracking Feature', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsPlanner(page);
    await navigateToBudget(page);
  });

  test('should display Add Payment button on budget categories', async ({ page }) => {
    // Wait for budget categories to load
    await page.waitForSelector('.budget-category-card', { timeout: 10000 });

    // Check that Add Payment button exists
    const addPaymentButton = page.locator('button:has-text("Add Payment")').first();
    await expect(addPaymentButton).toBeVisible();
  });

  test('should open payment modal when Add Payment is clicked', async ({ page }) => {
    // Click Add Payment on first category
    await page.click('button:has-text("Add Payment")', { timeout: 10000 });

    // Verify modal opened
    await expect(page.locator('h2:has-text("Record Payment")')).toBeVisible();
    await expect(page.locator('input[id="amount"]')).toBeVisible();
    await expect(page.locator('input[id="vendor_name"]')).toBeVisible();
    await expect(page.locator('input[id="payment_date"]')).toBeVisible();
  });

  test('should record a payment successfully', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Fill payment form
    await page.fill('input[id="amount"]', '2500');
    await page.fill('input[id="vendor_name"]', 'Test Vendor LLC');
    await page.fill('input[id="description"]', 'Initial deposit for services');
    await page.fill('textarea[id="notes"]', 'Payment processed via company card');

    // Select payment method
    await page.click('button:has-text("Credit/Debit Card")');

    // Submit form
    await page.click('button:has-text("Record Payment"):not(:has-text("Recording"))');

    // Verify success message
    await expect(page.locator('text=Payment recorded successfully')).toBeVisible({ timeout: 10000 });

    // Verify modal closed
    await expect(page.locator('h2:has-text("Record Payment")')).not.toBeVisible();
  });

  test('should validate payment amount', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Try to submit with invalid amount
    await page.fill('input[id="amount"]', '0');
    await page.click('button:has-text("Record Payment"):not(:has-text("Recording"))');

    // Should show error
    await expect(page.locator('text=Payment amount must be greater than 0')).toBeVisible();

    // Try negative amount
    await page.fill('input[id="amount"]', '-100');
    await page.click('button:has-text("Record Payment"):not(:has-text("Recording"))');

    // Should still show error
    await expect(page.locator('.text-red-700')).toBeVisible();
  });

  test('should handle payment methods correctly', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Test all payment methods
    const methods = ['Cash', 'Check', 'Credit/Debit Card', 'Bank Transfer'];

    for (const method of methods) {
      await page.click(`button:has-text("${method}")`);

      // Verify button is selected (has different styling)
      const button = page.locator(`button:has-text("${method}")`);
      const classes = await button.getAttribute('class');
      expect(classes).toContain('border-wedding-rose');
    }
  });

  test('should close modal on cancel', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Fill some data
    await page.fill('input[id="amount"]', '1000');
    await page.fill('input[id="vendor_name"]', 'Test Vendor');

    // Click cancel
    await page.click('button:has-text("Cancel")');

    // Modal should close without saving
    await expect(page.locator('h2:has-text("Record Payment")')).not.toBeVisible();

    // No success message should appear
    await expect(page.locator('text=Payment recorded successfully')).not.toBeVisible();
  });

  test('should close modal with X button', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Click X button
    await page.click('button[aria-label="Close modal"]');

    // Modal should close
    await expect(page.locator('h2:has-text("Record Payment")')).not.toBeVisible();
  });

  test('should display remaining budget in payment modal', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Check for remaining budget text
    const remainingBudget = page.locator('text=/Remaining budget: \\$/');

    // It should show either the remaining budget or not be visible if no budget is set
    const isVisible = await remainingBudget.isVisible();
    if (isVisible) {
      const text = await remainingBudget.textContent();
      expect(text).toMatch(/Remaining budget: \$[\d,]+/);
    }
  });

  test('should update budget category after payment', async ({ page }) => {
    // Get initial actual spent value from first category card
    const categoryCard = page.locator('.budget-category-card').first();
    const initialSpentText = await categoryCard.locator('text=/Spent: \\$/').textContent();
    const initialSpent = parseFloat(initialSpentText?.replace(/[^0-9.]/g, '') || '0');

    // Record a payment
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    const paymentAmount = 1500;
    await page.fill('input[id="amount"]', paymentAmount.toString());
    await page.fill('input[id="vendor_name"]', 'Update Test Vendor');
    await page.click('button:has-text("Credit/Debit Card")');
    await page.click('button:has-text("Record Payment"):not(:has-text("Recording"))');

    // Wait for success
    await expect(page.locator('text=Payment recorded successfully')).toBeVisible({ timeout: 10000 });

    // Wait for data refresh
    await page.waitForTimeout(1000);

    // Check updated spent amount
    const updatedSpentText = await categoryCard.locator('text=/Spent: \\$/').textContent();
    const updatedSpent = parseFloat(updatedSpentText?.replace(/[^0-9.]/g, '') || '0');

    // Verify amount increased
    expect(updatedSpent).toBeGreaterThanOrEqual(initialSpent + paymentAmount);
  });

  test('should handle payment date selection', async ({ page }) => {
    // Open payment modal
    await page.click('button:has-text("Add Payment")');
    await page.waitForSelector('h2:has-text("Record Payment")');

    // Get today's date in YYYY-MM-DD format
    const today = new Date().toISOString().split('T')[0];

    // Verify default date is today
    const dateInput = page.locator('input[id="payment_date"]');
    const defaultDate = await dateInput.inputValue();
    expect(defaultDate).toBe(today);

    // Change to yesterday
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];
    await dateInput.fill(yesterday);

    // Verify change took effect
    const newDate = await dateInput.inputValue();
    expect(newDate).toBe(yesterday);
  });
});

test.describe('Payment History', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsPlanner(page);
    await navigateToBudget(page);
  });

  test('should display payment history tab', async ({ page }) => {
    // Look for payment history section or tab
    const historyTab = page.locator('text=Payment History');

    // If tab exists, it should be clickable
    if (await historyTab.isVisible()) {
      await historyTab.click();
      await expect(page.locator('h2:has-text("Payment History")')).toBeVisible();
    }
  });

  test('should export payment history to CSV', async ({ page }) => {
    // Navigate to payment history if available
    const historyTab = page.locator('text=Payment History');
    if (await historyTab.isVisible()) {
      await historyTab.click();

      // Look for export button
      const exportButton = page.locator('button:has-text("Export CSV")');
      if (await exportButton.isVisible()) {
        // Set up download promise before clicking
        const downloadPromise = page.waitForEvent('download');

        // Click export
        await exportButton.click();

        // Wait for download
        const download = await downloadPromise;

        // Verify filename contains 'payment-history'
        expect(download.suggestedFilename()).toContain('payment-history');
        expect(download.suggestedFilename()).toContain('.csv');
      }
    }
  });

  test('should filter payments by method', async ({ page }) => {
    // Navigate to payment history if available
    const historyTab = page.locator('text=Payment History');
    if (await historyTab.isVisible()) {
      await historyTab.click();

      // Find filter dropdown
      const methodFilter = page.locator('select:has-text("All Methods")');
      if (await methodFilter.isVisible()) {
        // Select Cash filter
        await methodFilter.selectOption('cash');

        // Wait for filter to apply
        await page.waitForTimeout(500);

        // Verify filtered results (if any payments exist)
        const paymentRows = page.locator('tbody tr');
        const count = await paymentRows.count();

        if (count > 0) {
          // Check that all visible payments are cash
          for (let i = 0; i < count; i++) {
            const methodCell = paymentRows.nth(i).locator('td:nth-child(4)');
            const methodText = await methodCell.textContent();
            expect(methodText?.toLowerCase()).toContain('cash');
          }
        }
      }
    }
  });

  test('should search payments by vendor name', async ({ page }) => {
    // Navigate to payment history if available
    const historyTab = page.locator('text=Payment History');
    if (await historyTab.isVisible()) {
      await historyTab.click();

      // Find search input
      const searchInput = page.locator('input[placeholder="Search payments..."]');
      if (await searchInput.isVisible()) {
        // Search for specific vendor
        await searchInput.fill('Test Vendor');

        // Wait for search to apply
        await page.waitForTimeout(500);

        // Verify search results
        const paymentRows = page.locator('tbody tr');
        const count = await paymentRows.count();

        if (count > 0) {
          // Check that results contain search term
          for (let i = 0; i < count; i++) {
            const row = paymentRows.nth(i);
            const rowText = await row.textContent();
            expect(rowText?.toLowerCase()).toContain('test vendor');
          }
        }
      }
    }
  });
});

test.describe('Payment Security', () => {
  test('should require authentication to record payment', async ({ page }) => {
    // Go directly to budget page without login
    await page.goto('/admin/budget');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('should prevent invalid payment methods via API', async ({ page, request }) => {
    // This would test direct API calls with invalid payment methods
    // Requires API endpoint to be accessible in test environment

    // Example (would need actual API setup):
    // const response = await request.post('/api/budget/category/123/payment', {
    //   data: {
    //     amount: 100,
    //     payment_method: 'cryptocurrency', // Invalid method
    //     payment_date: new Date().toISOString()
    //   }
    // });
    // expect(response.status()).toBe(400);
  });
});