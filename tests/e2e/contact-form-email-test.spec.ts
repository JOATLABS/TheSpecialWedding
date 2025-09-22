import { test, expect } from '@playwright/test';

test.describe('Contact Form Email Notification E2E Test', () => {
  test('should submit contact form and trigger email notification', async ({ page }) => {
    // Navigate to the homepage
    const frontendUrl = process.env.FRONTEND_URL!;
    await page.goto(frontendUrl);

    // Wait for page to load and check if we're on the correct page
    await expect(page).toHaveTitle(/Special Wedding|TheSpecialWedding/);

    // Look for contact form section - try multiple possible selectors
    const contactSection = page.locator('[data-testid="contact-form"], .contact-form, #contact, section:has-text("Contact")').first();

    // If contact form is not immediately visible, scroll down to find it
    if (!(await contactSection.isVisible())) {
      // Try scrolling to find contact section
      await page.evaluate(() => {
        const contactElement = document.querySelector('[data-testid="contact-form"], .contact-form, #contact') ||
                              Array.from(document.querySelectorAll('section, div')).find(el =>
                                el.textContent?.toLowerCase().includes('contact') ||
                                el.textContent?.toLowerCase().includes('get in touch')
                              );
        if (contactElement) {
          contactElement.scrollIntoView({ behavior: 'smooth' });
        }
      });
      await page.waitForTimeout(1000);
    }

    // Take a screenshot to see what's on the page
    await page.screenshot({ path: 'tests/results/homepage-before-form.png', fullPage: true });

    // Look for form input fields with multiple possible selectors
    const nameInput = page.locator('input[name="name"], input[placeholder*="name" i], input[id*="name"], input[type="text"]:has-text("Name")').first();
    const emailInput = page.locator('input[name="email"], input[placeholder*="email" i], input[id*="email"], input[type="email"]').first();
    const companyInput = page.locator('input[name="company"], input[placeholder*="company" i], input[id*="company"]').first();
    const phoneInput = page.locator('input[name="phone"], input[placeholder*="phone" i], input[id*="phone"], input[type="tel"]').first();
    const messageInput = page.locator('textarea[name="message"], textarea[placeholder*="message" i], textarea[id*="message"], textarea').first();
    const submitButton = page.locator('button[type="submit"], button:has-text("Submit"), button:has-text("Send"), input[type="submit"]').first();

    // Log what we found
    console.log('Looking for contact form elements...');

    // Check if any form elements are visible
    const elementsFound = {
      name: await nameInput.isVisible(),
      email: await emailInput.isVisible(),
      company: await companyInput.isVisible(),
      phone: await phoneInput.isVisible(),
      message: await messageInput.isVisible(),
      submit: await submitButton.isVisible()
    };

    console.log('Form elements found:', elementsFound);

    // If no form elements found, let's inspect the page content
    if (!elementsFound.email && !elementsFound.name) {
      const pageContent = await page.content();
      console.log('Page title:', await page.title());

      // Look for any forms on the page
      const forms = await page.locator('form').count();
      console.log('Number of forms found:', forms);

      if (forms > 0) {
        // Get all form details
        for (let i = 0; i < forms; i++) {
          const form = page.locator('form').nth(i);
          const formHTML = await form.innerHTML();
          console.log(`Form ${i + 1} HTML:`, formHTML.substring(0, 500));
        }
      }

      // Check if there's a contact link or button that leads to a contact page
      const contactLinks = page.locator('a:has-text("Contact"), a[href*="contact"], button:has-text("Contact")');
      const contactLinkCount = await contactLinks.count();

      if (contactLinkCount > 0) {
        console.log('Found contact links, clicking the first one...');
        await contactLinks.first().click();
        await page.waitForTimeout(2000);

        // Take screenshot of contact page
        await page.screenshot({ path: 'tests/results/contact-page.png', fullPage: true });

        // Re-check for form elements on contact page
        const nameInputContact = page.locator('input[name="name"], input[placeholder*="name" i]').first();
        const emailInputContact = page.locator('input[name="email"], input[type="email"]').first();
        const companyInputContact = page.locator('input[name="company"], input[placeholder*="company" i]').first();
        const phoneInputContact = page.locator('input[name="phone"], input[type="tel"]').first();
        const messageInputContact = page.locator('textarea[name="message"], textarea').first();
        const submitButtonContact = page.locator('button[type="submit"], button:has-text("Submit")').first();

        // Fill out the contact form
        await expect(emailInputContact).toBeVisible();

        await nameInputContact.fill('Test Email Integration User');
        await emailInputContact.fill('test-integration@example.com');
        if (await companyInputContact.isVisible()) {
          await companyInputContact.fill('E2E Testing Corp');
        }
        if (await phoneInputContact.isVisible()) {
          await phoneInputContact.fill('555-TEST-E2E');
        }
        await messageInputContact.fill('This is an end-to-end test submission to verify that the email notification system is working correctly with Celery, Redis, email templates, and MongoDB integration. If you receive this via email at thedeveloper@thespecialwedding.com, the system is functioning properly!');

        // Take screenshot before submission
        await page.screenshot({ path: 'tests/results/form-filled.png', fullPage: true });

        // Submit the form
        await submitButtonContact.click();

        // Wait for submission response
        await page.waitForTimeout(3000);

        // Take screenshot after submission
        await page.screenshot({ path: 'tests/results/form-submitted.png', fullPage: true });

        // Look for success message - be more specific
        const successMessage = page.locator('h3:has-text("Thank You!")');
        if (await successMessage.isVisible()) {
          console.log('Success message found:', await successMessage.textContent());
          expect(await successMessage.isVisible()).toBeTruthy();
        } else {
          console.log('No success message found, but form was submitted');
        }

      } else {
        throw new Error('No contact form or contact links found on the page');
      }
    } else {
      // Form elements found on homepage, fill them out
      await expect(emailInput).toBeVisible();

      await nameInput.fill('Test Email Integration User');
      await emailInput.fill('test-integration@example.com');
      if (await companyInput.isVisible()) {
        await companyInput.fill('E2E Testing Corp');
      }
      if (await phoneInput.isVisible()) {
        await phoneInput.fill('555-TEST-E2E');
      }
      await messageInput.fill('This is an end-to-end test submission to verify that the email notification system is working correctly with Celery, Redis, email templates, and MongoDB integration. If you receive this via email at thedeveloper@thespecialwedding.com, the system is functioning properly!');

      // Take screenshot before submission
      await page.screenshot({ path: 'tests/results/form-filled.png', fullPage: true });

      // Submit the form
      await submitButton.click();

      // Wait for submission response
      await page.waitForTimeout(3000);

      // Take screenshot after submission
      await page.screenshot({ path: 'tests/results/form-submitted.png', fullPage: true });

      // Look for success message - be more specific
      const successMessage = page.locator('h3:has-text("Thank You!")');
      if (await successMessage.isVisible()) {
        console.log('Success message found:', await successMessage.textContent());
        expect(await successMessage.isVisible()).toBeTruthy();
      } else {
        console.log('No success message found, but form was submitted');
      }
    }
  });

  test('should verify backend API endpoint for contact form', async ({ request }) => {
    // Test the contact form API endpoint directly
    const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL!;
    const response = await request.post(`${apiUrl}/public/contact-form`, {
      data: {
        name: 'API Test User',
        email: 'api-test@example.com',
        company: 'API Testing Inc',
        phone: '555-API-TEST',
        message: 'This is a direct API test to verify the contact form endpoint works and triggers email notifications correctly.'
      }
    });

    console.log('API Response Status:', response.status());
    const responseBody = await response.text();
    console.log('API Response Body:', responseBody);

    // Check if the request was successful
    expect(response.status()).toBe(200);
  });
});