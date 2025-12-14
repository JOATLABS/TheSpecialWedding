import { test, expect } from '@playwright/test';

test.describe('Wedding Planner Dashboard Loading Issue', () => {
  test('should debug dashboard loading problem for verified user', async ({ page }) => {
    // Enable console logging
    const consoleMessages: string[] = [];
    const networkRequests: any[] = [];
    const networkResponses: any[] = [];

    // Capture console messages
    page.on('console', msg => {
      consoleMessages.push(`${msg.type()}: ${msg.text()}`);
    });

    // Capture network requests and responses
    page.on('request', request => {
      networkRequests.push({
        url: request.url(),
        method: request.method(),
        headers: request.headers(),
        postData: request.postData()
      });
    });

    page.on('response', response => {
      networkResponses.push({
        url: response.url(),
        status: response.status(),
        statusText: response.statusText(),
        headers: response.headers()
      });
    });

    // Step 1: Navigate to login page
    await page.goto('/admin/login');
    await expect(page).toHaveTitle(/Wedding Admin/);

    // Step 2: Log in with the verified user credentials
    await page.fill('input[name="email"]', 'test.verification@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');

    // Submit login form
    await page.click('button[type="submit"]');

    // Wait for login to complete and redirect
    await page.waitForURL(/\/admin/, { timeout: 10000 });

    // Step 3: Navigate to wedding planner dashboard
    console.log('Navigating to wedding planner dashboard...');
    await page.goto('/admin/planner');

    // Step 4: Check if the loading state appears
    console.log('Checking for loading state...');
    const loadingElement = page.locator('text=Loading your weddings...');

    // Wait a bit to see if loading appears
    await page.waitForTimeout(1000);

    if (await loadingElement.isVisible()) {
      console.log('Loading state detected - monitoring for resolution...');

      // Wait up to 15 seconds for loading to complete
      try {
        await loadingElement.waitFor({ state: 'hidden', timeout: 15000 });
        console.log('Loading completed successfully');
      } catch (error) {
        console.log('Loading did not complete within 15 seconds - stuck in loading state');
      }
    } else {
      console.log('No loading state detected, dashboard may have loaded immediately');
    }

    // Step 5: Check the final state of the dashboard
    await page.waitForTimeout(2000); // Give time for any async operations

    const isStillLoading = await loadingElement.isVisible();
    const hasErrorMessage = await page.locator('.text-red-600').isVisible();
    const hasWeddingsList = await page.locator('text=Your Weddings').isVisible();
    const hasStatsCards = await page.locator('text=Active Weddings').isVisible();

    console.log('Dashboard State Analysis:');
    console.log(`- Still in loading state: ${isStillLoading}`);
    console.log(`- Has error message: ${hasErrorMessage}`);
    console.log(`- Has weddings list section: ${hasWeddingsList}`);
    console.log(`- Has stats cards: ${hasStatsCards}`);

    // Step 6: Check for the specific API call to /admin/planner/metrics
    const metricsApiCalls = networkRequests.filter(req =>
      req.url.includes('/admin/planner/metrics')
    );

    const metricsApiResponses = networkResponses.filter(res =>
      res.url.includes('/admin/planner/metrics')
    );

    console.log('API Analysis:');
    console.log(`- Metrics API calls made: ${metricsApiCalls.length}`);
    console.log(`- Metrics API responses received: ${metricsApiResponses.length}`);

    if (metricsApiCalls.length > 0) {
      console.log('Metrics API Call Details:');
      metricsApiCalls.forEach((call, index) => {
        console.log(`  Call ${index + 1}:`);
        console.log(`    URL: ${call.url}`);
        console.log(`    Method: ${call.method}`);
        console.log(`    Authorization Header: ${call.headers.authorization ? 'Present' : 'Missing'}`);
      });
    }

    if (metricsApiResponses.length > 0) {
      console.log('Metrics API Response Details:');
      for (const response of metricsApiResponses) {
        console.log(`  Response:`);
        console.log(`    URL: ${response.url}`);
        console.log(`    Status: ${response.status} ${response.statusText}`);

        // Try to get response body if possible
        try {
          const responseObj = networkResponses.find(r => r.url === response.url);
          if (responseObj) {
            // This is a simplified check - in a real scenario you'd need to capture response bodies
            console.log(`    Headers: ${JSON.stringify(response.headers, null, 2)}`);
          }
        } catch (error) {
          console.log(`    Could not read response body: ${error}`);
        }
      }
    } else if (metricsApiCalls.length > 0) {
      console.log('API calls were made but no responses received - this indicates a network or server issue');
    } else {
      console.log('No API calls to metrics endpoint detected - this indicates a client-side issue');
    }

    // Step 7: Check console logs for JavaScript errors
    const errorMessages = consoleMessages.filter(msg =>
      msg.includes('error:') || msg.includes('Error:') || msg.includes('Failed')
    );

    console.log('Console Error Analysis:');
    if (errorMessages.length > 0) {
      console.log(`- Found ${errorMessages.length} error messages:`);
      errorMessages.forEach((error, index) => {
        console.log(`  Error ${index + 1}: ${error}`);
      });
    } else {
      console.log('- No console errors detected');
    }

    // Step 8: Check for authentication issues
    const authRelatedErrors = networkResponses.filter(res =>
      res.status === 401 || res.status === 403
    );

    if (authRelatedErrors.length > 0) {
      console.log('Authentication Issues Detected:');
      authRelatedErrors.forEach((error, index) => {
        console.log(`  Auth Error ${index + 1}: ${error.status} ${error.statusText} - ${error.url}`);
      });
    }

    // Step 9: Check user profile and permissions
    console.log('Checking user profile and permissions...');

    // Look for any profile-related API calls
    const profileApiCalls = networkRequests.filter(req =>
      req.url.includes('/admin/profile') || req.url.includes('/admin/user')
    );

    console.log(`Profile API calls: ${profileApiCalls.length}`);

    // Step 10: Final diagnosis
    console.log('\n=== DIAGNOSIS SUMMARY ===');

    if (isStillLoading) {
      console.log('ISSUE CONFIRMED: Dashboard is stuck in loading state');

      if (metricsApiCalls.length === 0) {
        console.log('ROOT CAUSE: No API calls being made to metrics endpoint');
        console.log('LIKELY ISSUES:');
        console.log('- JavaScript error preventing API call');
        console.log('- Authentication token missing or invalid');
        console.log('- User profile not loaded or missing wedding planner permission');
      } else if (metricsApiResponses.length === 0) {
        console.log('ROOT CAUSE: API calls made but no responses received');
        console.log('LIKELY ISSUES:');
        console.log('- Server not responding');
        console.log('- Network connectivity issue');
        console.log('- CORS issues');
      } else {
        const failedResponses = metricsApiResponses.filter(r => r.status >= 400);
        if (failedResponses.length > 0) {
          console.log('ROOT CAUSE: API calls failing with error responses');
          console.log('LIKELY ISSUES:');
          console.log('- Authentication/authorization failure');
          console.log('- Server-side error in metrics endpoint');
          console.log('- Database connection issues');
        } else {
          console.log('ROOT CAUSE: API calls succeeding but UI not updating');
          console.log('LIKELY ISSUES:');
          console.log('- JavaScript error in response handling');
          console.log('- State management issue');
          console.log('- Response format mismatch');
        }
      }
    } else {
      console.log('Dashboard appears to be loading correctly');
    }

    // Assertions for the test
    if (isStillLoading) {
      // If stuck in loading, we want to fail the test but provide useful info
      throw new Error(
        `Dashboard stuck in loading state. ` +
        `API calls: ${metricsApiCalls.length}, ` +
        `API responses: ${metricsApiResponses.length}, ` +
        `Console errors: ${errorMessages.length}`
      );
    }

    // If not stuck in loading, verify the dashboard loaded properly
    await expect(page.locator('text=Your Weddings')).toBeVisible();
    await expect(page.locator('text=Active Weddings')).toBeVisible();
  });

  test('should directly test the metrics API endpoint', async ({ page, request }) => {
    // First login to get a token
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'test.verification@example.com');
    await page.fill('input[name="password"]', 'TestPassword123!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/admin/, { timeout: 10000 });

    // Extract the token from local storage or session storage
    const token = await page.evaluate(() => {
      return localStorage.getItem('adminToken') || sessionStorage.getItem('adminToken');
    });

    console.log(`Token found: ${token ? 'Yes' : 'No'}`);

    if (token) {
      // Test the API endpoint directly
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

      try {
        const response = await request.get(`${baseUrl}/admin/planner/metrics`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        console.log('Direct API Test Results:');
        console.log(`- Status: ${response.status()}`);
        console.log(`- Status Text: ${response.statusText()}`);

        if (response.ok()) {
          const data = await response.json();
          console.log(`- Response data structure:`, Object.keys(data));
          console.log(`- Weddings count: ${data.weddings?.length || 0}`);
          console.log(`- Summary present: ${!!data.summary}`);
        } else {
          const errorText = await response.text();
          console.log(`- Error response: ${errorText}`);
        }

      } catch (error) {
        console.log(`- API request failed: ${error}`);
      }
    } else {
      console.log('Could not extract authentication token from browser');
    }
  });
});