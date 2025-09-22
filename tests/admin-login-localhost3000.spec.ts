import { test, expect } from '@playwright/test';

test.describe('Admin Login Test - localhost:3000', () => {
  const adminCredentials = {
    email: 'thedeveloper@thespecialwedding.com',
    password: 'j89x8G&8SM8^m'
  };

  test('Test admin login functionality at localhost:3000', async ({ page }) => {
    // Enable console logging to capture any errors
    page.on('console', msg => {
      console.log(`CONSOLE ${msg.type()}: ${msg.text()}`);
    });

    // Capture network requests and responses for debugging
    page.on('request', request => {
      console.log(`REQUEST: ${request.method()} ${request.url()}`);
    });

    page.on('response', response => {
      console.log(`RESPONSE: ${response.status()} ${response.url()}`);
    });

    try {
      // Step 1: Navigate to admin page
      console.log('🔍 Step 1: Navigating to admin page...');
      await page.goto(`${process.env.FRONTEND_URL!}/admin`);
      
      // Wait for page to load
      await page.waitForTimeout(2000);
      
      // Take screenshot of the admin page
      await page.screenshot({ 
        path: 'admin-page-initial.png', 
        fullPage: true 
      });
      
      console.log(`Current URL: ${page.url()}`);
      console.log(`Page title: ${await page.title()}`);

      // Check if we're redirected to login or if we're already on an admin page
      const currentUrl = page.url();
      if (currentUrl.includes('/login')) {
        console.log('🔄 Redirected to login page - this is expected');
      } else if (currentUrl.includes('/admin')) {
        console.log('✅ Already on admin page - might be already authenticated');
      }

      // Step 2: If on login page, fill in the login form
      const emailInput = page.locator('input[type="email"]');
      const passwordInput = page.locator('input[type="password"]');
      const loginButton = page.locator('button:has-text("Log In"), button:has-text("Login"), button:has-text("Sign In")');

      if (await emailInput.count() > 0 && await passwordInput.count() > 0) {
        console.log('🔍 Step 2: Login form found, filling credentials...');
        
        // Fill in the credentials
        await emailInput.fill(adminCredentials.email);
        await passwordInput.fill(adminCredentials.password);
        
        console.log('✅ Credentials filled successfully');
        
        // Take screenshot of filled form
        await page.screenshot({ 
          path: 'login-form-filled.png', 
          fullPage: true 
        });

        // Step 3: Submit the form
        if (await loginButton.count() > 0) {
          console.log('🔍 Step 3: Submitting login form...');
          await loginButton.click();
          
          // Wait for navigation or response
          await page.waitForTimeout(3000);
          
          const afterLoginUrl = page.url();
          console.log(`URL after login: ${afterLoginUrl}`);
          
          // Take screenshot after login attempt
          await page.screenshot({ 
            path: 'after-login-result.png', 
            fullPage: true 
          });
        } else {
          console.log('❌ Login button not found');
        }
      } else {
        console.log('ℹ️ No login form found - might already be authenticated');
      }

      // Step 4: Verify login success by checking if we're on admin dashboard
      const finalUrl = page.url();
      console.log('🔍 Step 4: Verifying login success...');
      
      if (finalUrl.includes('/admin') && !finalUrl.includes('/login')) {
        console.log('✅ Login successful - on admin area');
        
        // Step 5: Check what navigation items are visible
        console.log('🔍 Step 5: Checking navigation items...');
        
        // Look for common admin navigation patterns
        const navItems = await page.locator('nav a, [role="navigation"] a, .nav-item, .navigation a').allTextContents();
        const menuItems = await page.locator('ul li a, .menu a, .sidebar a').allTextContents();
        const buttonTexts = await page.locator('button').allTextContents();
        
        console.log('Navigation items found:', navItems.filter(text => text.trim().length > 0));
        console.log('Menu items found:', menuItems.filter(text => text.trim().length > 0));
        console.log('Button texts found:', buttonTexts.filter(text => text.trim().length > 0));
        
        // Look for specific admin sections
        const adminSections = [
          'Dashboard', 'Metrics', 'Weddings', 'Guests', 'Forms', 'Budget', 
          'Gallery', 'Users', 'SaaS', 'Vendors', 'Subscriptions'
        ];
        
        console.log('🔍 Checking for admin sections...');
        for (const section of adminSections) {
          const sectionExists = await page.locator(`text=${section}`).count() > 0;
          if (sectionExists) {
            console.log(`✅ Found: ${section}`);
          }
        }

        // Step 6: Try to navigate to /admin/metrics
        console.log('🔍 Step 6: Testing navigation to /admin/metrics...');
        try {
          await page.goto('http://localhost:3000/admin/metrics');
          await page.waitForTimeout(2000);
          
          const metricsUrl = page.url();
          console.log(`Metrics page URL: ${metricsUrl}`);
          
          // Take screenshot of metrics page
          await page.screenshot({ 
            path: 'admin-metrics-page.png', 
            fullPage: true 
          });
          
          if (metricsUrl.includes('/metrics')) {
            console.log('✅ Successfully navigated to metrics page');
          } else {
            console.log('⚠️ Metrics page navigation might have redirected');
          }
        } catch (error) {
          console.log('❌ Error navigating to metrics page:', error);
        }

        // Take final screenshot of the admin interface
        await page.screenshot({ 
          path: 'final-admin-interface.png', 
          fullPage: true 
        });

      } else if (finalUrl.includes('/login')) {
        console.log('❌ Login failed - still on login page');
        
        // Check for error messages
        const errorMessages = await page.locator('.error, .alert-danger, .text-red, [role="alert"]').allTextContents();
        if (errorMessages.length > 0) {
          console.log('Error messages found:', errorMessages);
        }
      } else {
        console.log('⚠️ Unexpected URL after login:', finalUrl);
      }

    } catch (error) {
      console.log('❌ Test error:', error);
      
      // Take screenshot of error state
      await page.screenshot({ 
        path: 'error-state.png', 
        fullPage: true 
      });
      
      // Check if backend is running
      try {
        const backendResponse = await page.request.get('http://localhost:8000/health');
        console.log('Backend (port 8000) status:', backendResponse.status());
      } catch (backendError) {
        console.log('❌ Backend not responding on port 8000');
      }

      try {
        const backendResponse = await page.request.get('http://localhost:8002/health');
        console.log('Backend (port 8002) status:', backendResponse.status());
      } catch (backendError) {
        console.log('❌ Backend not responding on port 8002');
      }
    }
  });
});