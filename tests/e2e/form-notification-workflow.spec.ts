import { test, expect, Page } from '@playwright/test';

test.describe('Form Notification Workflow', () => {
  let adminPage: Page;
  let userPage: Page;
  let formId: string;
  let formUrl: string;

  test.beforeAll(async ({ browser }) => {
    // Create separate browser contexts for admin and user
    const adminContext = await browser.newContext();
    const userContext = await browser.newContext();

    adminPage = await adminContext.newPage();
    userPage = await userContext.newPage();
  });

  test.afterAll(async () => {
    await adminPage?.close();
    await userPage?.close();
  });

  test('Complete form notification workflow', async () => {
    // Step 1: Admin logs in and creates a form
    await test.step('Admin creates form', async () => {
      await adminPage.goto('/admin/login');

      // Login as admin using credentials from environment
      await adminPage.fill('[data-testid="email-input"]', process.env.TEST_PLANNER_EMAIL!);
      await adminPage.fill('[data-testid="password-input"]', process.env.TEST_PLANNER_PASSWORD!);
      await adminPage.click('[data-testid="login-button"]');

      // Wait for dashboard
      await expect(adminPage).toHaveURL('/admin');

      // Navigate to forms
      await adminPage.click('[data-testid="forms-nav-link"]');
      await expect(adminPage).toHaveURL('/admin/forms');

      // Create new form
      await adminPage.click('[data-testid="create-form-button"]');

      // Fill form details
      await adminPage.fill('[data-testid="form-name-input"]', 'Wedding Feedback Test Form');
      await adminPage.fill('[data-testid="form-title-input"]', 'How was your wedding experience?');
      await adminPage.fill('[data-testid="form-description-input"]', 'Please share your feedback with us');

      // Add rating field
      await adminPage.click('[data-testid="add-field-button"]');
      await adminPage.selectOption('[data-testid="field-type-select"]', 'rating');
      await adminPage.fill('[data-testid="field-label-input"]', 'Overall Rating');
      await adminPage.fill('[data-testid="field-id-input"]', 'overall_rating');
      await adminPage.check('[data-testid="field-required-checkbox"]');
      await adminPage.click('[data-testid="add-field-confirm"]');

      // Add feedback field
      await adminPage.click('[data-testid="add-field-button"]');
      await adminPage.selectOption('[data-testid="field-type-select"]', 'textarea');
      await adminPage.fill('[data-testid="field-label-input"]', 'Additional Comments');
      await adminPage.fill('[data-testid="field-id-input"]', 'feedback_text');
      await adminPage.click('[data-testid="add-field-confirm"]');

      // Save form
      await adminPage.click('[data-testid="save-form-button"]');

      // Wait for success message and capture form ID
      await expect(adminPage.locator('[data-testid="success-message"]')).toBeVisible();

      // Extract form ID from URL or response
      const url = adminPage.url();
      const formIdMatch = url.match(/\/forms\/([^\/]+)/);
      formId = formIdMatch ? formIdMatch[1] : '';
      expect(formId).toBeTruthy();

      formUrl = `/public/forms/${formId}`;
    });

    // Step 2: Admin enables notification preferences
    await test.step('Admin enables notifications', async () => {
      // Navigate to profile settings
      await adminPage.click('[data-testid="profile-menu"]');
      await adminPage.click('[data-testid="account-settings-link"]');
      await expect(adminPage).toHaveURL('/admin/profile');

      // Switch to notifications tab
      await adminPage.click('[data-testid="notifications-tab"]');

      // Enable email notifications
      const emailToggle = adminPage.locator('[data-testid="email-enabled-toggle"]');
      if (!(await emailToggle.isChecked())) {
        await emailToggle.click();
      }

      // Enable instant notifications
      const instantToggle = adminPage.locator('[data-testid="instant-notifications-toggle"]');
      if (!(await instantToggle.isChecked())) {
        await instantToggle.click();
      }

      // Save preferences
      await adminPage.click('[data-testid="save-preferences-button"]');
      await expect(adminPage.locator('[data-testid="success-toast"]')).toBeVisible();
    });

    // Step 3: Verify initial state - no unread responses
    await test.step('Verify initial unread count', async () => {
      // Navigate to forms list
      await adminPage.goto('/admin/forms');

      // Should show 0 unread responses initially
      const unreadBadge = adminPage.locator('[data-testid="unread-responses-badge"]');
      await expect(unreadBadge).not.toBeVisible();
    });

    // Step 4: User submits form response
    await test.step('User submits form response', async () => {
      // User navigates to public form
      await userPage.goto(formUrl);

      // Wait for form to load
      await expect(userPage.locator('[data-testid="form-title"]')).toHaveText('How was your wedding experience?');

      // Fill out form
      await userPage.fill('[data-testid="submitted-by-name"]', 'Sarah Johnson');
      await userPage.fill('[data-testid="submitted-by-email"]', 'sarah.johnson@example.com');

      // Set rating (click 5th star)
      await userPage.click('[data-testid="rating-star-5"]');

      // Fill feedback
      await userPage.fill('[data-testid="feedback-text-textarea"]', 'Absolutely amazing experience! The planning was flawless and everything went perfectly. Thank you so much!');

      // Submit form
      await userPage.click('[data-testid="submit-form-button"]');

      // Wait for success message
      await expect(userPage.locator('[data-testid="form-success-message"]')).toBeVisible();
      await expect(userPage.locator('[data-testid="form-success-message"]')).toHaveText('Thank you for your submission!');
    });

    // Step 5: Admin sees notification badge
    await test.step('Admin sees unread notification badge', async () => {
      // Refresh admin forms page
      await adminPage.goto('/admin/forms');

      // Should show 1 unread response
      const unreadBadge = adminPage.locator('[data-testid="unread-responses-badge"]');
      await expect(unreadBadge).toBeVisible();
      await expect(unreadBadge).toHaveText('1');

      // Badge should have notification styling (pulse animation)
      await expect(unreadBadge).toHaveClass(/animate-pulse/);
    });

    // Step 6: Admin views form responses
    await test.step('Admin views form responses', async () => {
      // Click on the form to view responses
      await adminPage.click(`[data-testid="form-card-${formId}"]`);
      await adminPage.click('[data-testid="view-responses-button"]');

      // Should be on responses page
      await expect(adminPage).toHaveURL(`/admin/forms/${formId}/responses`);

      // Should show 1 response
      await expect(adminPage.locator('[data-testid="response-count"]')).toHaveText('1 responses');

      // Should show unread badge in header
      const headerBadge = adminPage.locator('[data-testid="form-unread-badge"]');
      await expect(headerBadge).toBeVisible();
      await expect(headerBadge).toHaveText('1 unread');

      // Response row should have unread styling (blue background)
      const responseRow = adminPage.locator('[data-testid="response-row"]').first();
      await expect(responseRow).toHaveClass(/bg-blue-50/);

      // Should show unread badge in status column
      const statusBadge = responseRow.locator('[data-testid="response-status-badge"]');
      await expect(statusBadge).toHaveText('Unread');
      await expect(statusBadge).toHaveClass(/bg-wedding-rose/);
    });

    // Step 7: Admin views response details
    await test.step('Admin views response details', async () => {
      // Click "View Details" button
      await adminPage.click('[data-testid="view-details-button"]');

      // Modal should open
      const modal = adminPage.locator('[data-testid="response-details-modal"]');
      await expect(modal).toBeVisible();

      // Should show response data
      await expect(modal.locator('[data-testid="submitted-by-name"]')).toHaveText('Sarah Johnson');
      await expect(modal.locator('[data-testid="submitted-by-email"]')).toHaveText('sarah.johnson@example.com');
      await expect(modal.locator('[data-testid="overall-rating-value"]')).toHaveText('5');
      await expect(modal.locator('[data-testid="feedback-text-value"]')).toContain('Absolutely amazing experience!');

      // Should show unread status in modal
      const modalStatusBadge = modal.locator('[data-testid="modal-status-badge"]');
      await expect(modalStatusBadge).toHaveText('Unread');
    });

    // Step 8: Admin marks response as reviewed
    await test.step('Admin marks response as reviewed', async () => {
      // Click "Mark as Read" button in modal
      const markReadButton = adminPage.locator('[data-testid="mark-read-button"]');
      await expect(markReadButton).toHaveText('Mark as Read');
      await markReadButton.click();

      // Button should change to "Mark as Unread"
      await expect(markReadButton).toHaveText('Mark as Unread');

      // Status badge should update
      const modalStatusBadge = adminPage.locator('[data-testid="modal-status-badge"]');
      await expect(modalStatusBadge).toHaveText('Read');
      await expect(modalStatusBadge).toHaveClass(/bg-gray-100/);

      // Close modal
      await adminPage.click('[data-testid="close-modal-button"]');
    });

    // Step 9: Verify response marked as read
    await test.step('Verify response marked as read', async () => {
      // Response row should no longer have unread styling
      const responseRow = adminPage.locator('[data-testid="response-row"]').first();
      await expect(responseRow).not.toHaveClass(/bg-blue-50/);

      // Status badge should show "Read"
      const statusBadge = responseRow.locator('[data-testid="response-status-badge"]');
      await expect(statusBadge).toHaveText('Read');
      await expect(statusBadge).toHaveClass(/bg-gray-100/);

      // Header unread badge should be gone
      const headerBadge = adminPage.locator('[data-testid="form-unread-badge"]');
      await expect(headerBadge).not.toBeVisible();
    });

    // Step 10: Verify global unread count updated
    await test.step('Verify global unread count updated', async () => {
      // Navigate back to forms list
      await adminPage.goto('/admin/forms');

      // Unread badge should be gone
      const unreadBadge = adminPage.locator('[data-testid="unread-responses-badge"]');
      await expect(unreadBadge).not.toBeVisible();
    });

    // Step 11: Test marking as unread again
    await test.step('Test mark as unread functionality', async () => {
      // Go back to responses page
      await adminPage.goto(`/admin/forms/${formId}/responses`);

      // Click "Mark Unread" button in response row
      const markUnreadButton = adminPage.locator('[data-testid="mark-unread-button"]');
      await markUnreadButton.click();

      // Should show loading state briefly
      const loadingSpinner = adminPage.locator('[data-testid="updating-spinner"]');

      // Response should become unread again
      const responseRow = adminPage.locator('[data-testid="response-row"]').first();
      await expect(responseRow).toHaveClass(/bg-blue-50/);

      // Status should be unread
      const statusBadge = responseRow.locator('[data-testid="response-status-badge"]');
      await expect(statusBadge).toHaveText('Unread');

      // Header badge should return
      const headerBadge = adminPage.locator('[data-testid="form-unread-badge"]');
      await expect(headerBadge).toBeVisible();
      await expect(headerBadge).toHaveText('1 unread');
    });

    // Step 12: Test filtering by read/unread status
    await test.step('Test status filtering', async () => {
      // Filter to show only unread
      await adminPage.selectOption('[data-testid="status-filter-select"]', 'unreviewed');

      // Should show 1 response
      await expect(adminPage.locator('[data-testid="filtered-count"]')).toHaveText('Showing 1 of 1 responses');

      // Filter to show only read
      await adminPage.selectOption('[data-testid="status-filter-select"]', 'reviewed');

      // Should show 0 responses
      await expect(adminPage.locator('[data-testid="filtered-count"]')).toHaveText('Showing 0 of 1 responses');
      await expect(adminPage.locator('[data-testid="no-responses-message"]')).toBeVisible();

      // Reset filter to show all
      await adminPage.selectOption('[data-testid="status-filter-select"]', 'all');
      await expect(adminPage.locator('[data-testid="filtered-count"]')).toHaveText('Showing 1 of 1 responses');
    });

    // Step 13: Test "Unread first" sorting
    await test.step('Test unread first sorting', async () => {
      // Change sort to "Unread first"
      await adminPage.selectOption('[data-testid="sort-select"]', 'reviewed');

      // Response should still be visible (only one response)
      const responseRow = adminPage.locator('[data-testid="response-row"]').first();
      await expect(responseRow).toBeVisible();

      // Should have unread styling since it's unread
      await expect(responseRow).toHaveClass(/bg-blue-50/);
    });
  });

  test('Notification preferences workflow', async () => {
    // Step 1: Navigate to notification preferences
    await test.step('Navigate to notification preferences', async () => {
      await adminPage.goto('/admin/profile');

      // Click notifications tab
      await adminPage.click('[data-testid="notifications-tab"]');

      // Should show notification preferences form
      await expect(adminPage.locator('[data-testid="notification-preferences-form"]')).toBeVisible();
    });

    // Step 2: Test email notification toggle
    await test.step('Test email notification toggle', async () => {
      const emailToggle = adminPage.locator('[data-testid="email-enabled-toggle"]');

      // Toggle off
      await emailToggle.click();

      // Instant notifications section should be hidden
      await expect(adminPage.locator('[data-testid="instant-notifications-section"]')).not.toBeVisible();

      // Toggle back on
      await emailToggle.click();

      // Instant notifications section should be visible
      await expect(adminPage.locator('[data-testid="instant-notifications-section"]')).toBeVisible();
    });

    // Step 3: Test instant vs digest notifications
    await test.step('Test instant vs digest notifications', async () => {
      const instantToggle = adminPage.locator('[data-testid="instant-notifications-toggle"]');

      // Turn off instant notifications
      if (await instantToggle.isChecked()) {
        await instantToggle.click();
      }

      // Digest frequency section should be visible
      await expect(adminPage.locator('[data-testid="digest-frequency-section"]')).toBeVisible();

      // Test digest frequency options
      await adminPage.selectOption('[data-testid="digest-frequency-select"]', 'weekly');
      await adminPage.selectOption('[data-testid="digest-frequency-select"]', 'daily');
      await adminPage.selectOption('[data-testid="digest-frequency-select"]', 'none');

      // Turn instant notifications back on
      await instantToggle.click();

      // Digest frequency section should be hidden
      await expect(adminPage.locator('[data-testid="digest-frequency-section"]')).not.toBeVisible();
    });

    // Step 4: Test form-specific preferences
    await test.step('Test form-specific preferences', async () => {
      const formCheckbox = adminPage.locator(`[data-testid="form-checkbox-${formId}"]`);

      if (await formCheckbox.isVisible()) {
        // Select specific form
        await formCheckbox.check();

        // Save preferences
        await adminPage.click('[data-testid="save-preferences-button"]');
        await expect(adminPage.locator('[data-testid="success-toast"]')).toBeVisible();

        // Reload page and verify persistence
        await adminPage.reload();
        await adminPage.click('[data-testid="notifications-tab"]');

        // Checkbox should still be checked
        await expect(formCheckbox).toBeChecked();
      }
    });

    // Step 5: Test preferences persistence
    await test.step('Test preferences persistence', async () => {
      // Set specific preferences
      const emailToggle = adminPage.locator('[data-testid="email-enabled-toggle"]');
      const instantToggle = adminPage.locator('[data-testid="instant-notifications-toggle"]');

      // Ensure email is enabled and instant is disabled
      if (!(await emailToggle.isChecked())) {
        await emailToggle.click();
      }
      if (await instantToggle.isChecked()) {
        await instantToggle.click();
      }

      // Set digest to weekly
      await adminPage.selectOption('[data-testid="digest-frequency-select"]', 'weekly');

      // Save preferences
      await adminPage.click('[data-testid="save-preferences-button"]');
      await expect(adminPage.locator('[data-testid="success-toast"]')).toBeVisible();

      // Navigate away and back
      await adminPage.goto('/admin/forms');
      await adminPage.goto('/admin/profile');
      await adminPage.click('[data-testid="notifications-tab"]');

      // Verify preferences were saved
      await expect(emailToggle).toBeChecked();
      await expect(instantToggle).not.toBeChecked();
      await expect(adminPage.locator('[data-testid="digest-frequency-select"]')).toHaveValue('weekly');
    });
  });

  test('Mobile responsive notification interface', async () => {
    // Step 1: Test mobile form responses interface
    await test.step('Test mobile form responses', async () => {
      // Set mobile viewport
      await adminPage.setViewportSize({ width: 375, height: 667 });

      // Navigate to responses page
      await adminPage.goto(`/admin/forms/${formId}/responses`);

      // Mobile card view should be visible
      await expect(adminPage.locator('[data-testid="mobile-response-cards"]')).toBeVisible();

      // Desktop table should be hidden
      await expect(adminPage.locator('[data-testid="desktop-response-table"]')).not.toBeVisible();

      // Badge should still be visible and readable
      const mobileBadge = adminPage.locator('[data-testid="mobile-status-badge"]');
      await expect(mobileBadge).toBeVisible();
      await expect(mobileBadge).toHaveText('Unread');
    });

    // Step 2: Test mobile notification preferences
    await test.step('Test mobile notification preferences', async () => {
      // Navigate to profile
      await adminPage.goto('/admin/profile');

      // Mobile dropdown should be visible
      await expect(adminPage.locator('[data-testid="mobile-tab-select"]')).toBeVisible();

      // Desktop tabs should be hidden
      await expect(adminPage.locator('[data-testid="desktop-tabs"]')).not.toBeVisible();

      // Select notifications from dropdown
      await adminPage.selectOption('[data-testid="mobile-tab-select"]', 'notifications');

      // Notification preferences should be visible
      await expect(adminPage.locator('[data-testid="notification-preferences-form"]')).toBeVisible();

      // Toggle switches should be touch-friendly
      const emailToggle = adminPage.locator('[data-testid="email-enabled-toggle"]');
      await expect(emailToggle).toHaveCSS('height', '24px'); // Touch-friendly size
    });

    // Step 3: Reset to desktop viewport
    await test.step('Reset to desktop viewport', async () => {
      await adminPage.setViewportSize({ width: 1280, height: 720 });
    });
  });

  test('Dark mode notification interface', async () => {
    // Step 1: Enable dark mode
    await test.step('Enable dark mode', async () => {
      // Add dark class to document
      await adminPage.addStyleTag({
        content: `
          html { color-scheme: dark; }
          .dark { color-scheme: dark; }
        `
      });

      await adminPage.evaluate(() => {
        document.documentElement.classList.add('dark');
      });
    });

    // Step 2: Test dark mode on responses page
    await test.step('Test dark mode responses page', async () => {
      await adminPage.goto(`/admin/forms/${formId}/responses`);

      // Background should be dark
      const responseContainer = adminPage.locator('[data-testid="responses-container"]');
      await expect(responseContainer).toHaveClass(/dark:bg-gray-800/);

      // Text should be light
      const responseText = adminPage.locator('[data-testid="response-text"]').first();
      await expect(responseText).toHaveClass(/dark:text-gray-100/);

      // Badges should have dark mode styling
      const statusBadge = adminPage.locator('[data-testid="response-status-badge"]').first();
      await expect(statusBadge).toBeVisible();
    });

    // Step 3: Test dark mode on notification preferences
    await test.step('Test dark mode notification preferences', async () => {
      await adminPage.goto('/admin/profile');
      await adminPage.click('[data-testid="notifications-tab"]');

      // Form should have dark background
      const preferencesForm = adminPage.locator('[data-testid="notification-preferences-form"]');
      await expect(preferencesForm).toHaveClass(/dark:bg-gray-800/);

      // Toggle switches should have dark mode styling
      const emailToggle = adminPage.locator('[data-testid="email-enabled-toggle"]');
      await expect(emailToggle).toBeVisible();

      // Select elements should have dark styling
      const digestSelect = adminPage.locator('[data-testid="digest-frequency-select"]');
      await expect(digestSelect).toHaveClass(/dark:bg-gray-700/);
    });

    // Step 4: Disable dark mode
    await test.step('Disable dark mode', async () => {
      await adminPage.evaluate(() => {
        document.documentElement.classList.remove('dark');
      });
    });
  });
});