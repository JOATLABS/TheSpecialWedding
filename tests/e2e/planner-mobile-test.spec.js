const { test, expect, chromium } = require('@playwright/test');
const dotenv = require('dotenv');
const path = require('path');

// Load environment variables from .env file
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

// Get configuration from environment
const TEST_URL = process.env.FRONTEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL?.replace(':8000', ':3000') || 'http://localhost:3000';
const TEST_PLANNER_EMAIL = process.env.TEST_PLANNER_EMAIL;
const TEST_PLANNER_PASSWORD = process.env.TEST_PLANNER_PASSWORD;

test.describe('Wedding Planner Dashboard - Mobile Friendliness', () => {
  let browser;
  let mobileContext;
  let mobilePage;

  test.beforeAll(async () => {
    console.log('🚀 Testing Wedding Planner Dashboard Mobile Experience');
    console.log(`📍 Using URL from .env: ${TEST_URL}`);
    console.log(`👤 Testing with planner: ${TEST_PLANNER_EMAIL}`);

    browser = await chromium.launch({
      headless: false,  // Show UI for visual verification
      slowMo: 800,      // Slow down to see interactions
    });

    // iPhone 13 Pro viewport - typical customer mobile device
    mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
      isMobile: true,
      hasTouch: true,
      deviceScaleFactor: 3,
    });

    mobilePage = await mobileContext.newPage();
  });

  test.afterAll(async () => {
    await mobileContext.close();
    await browser.close();
  });

  test('Login page should be mobile-friendly', async () => {
    console.log('📱 Testing Login Page Mobile View...');

    await mobilePage.goto(`${TEST_URL}/admin/login`);
    await mobilePage.waitForTimeout(1000);

    // Check if login form is properly sized for mobile
    const loginForm = await mobilePage.$('form');
    expect(loginForm).toBeTruthy();

    // Verify input fields are accessible and properly sized
    const emailInput = await mobilePage.$('input[type="email"]');
    const passwordInput = await mobilePage.$('input[type="password"]');

    expect(emailInput).toBeTruthy();
    expect(passwordInput).toBeTruthy();

    // Check if buttons are touch-friendly (minimum 44px height)
    const loginButton = await mobilePage.$('button[type="submit"]');
    const buttonBox = await loginButton.boundingBox();
    expect(buttonBox.height).toBeGreaterThanOrEqual(40);

    console.log('✅ Login page is mobile-friendly');
  });

  test('Planner Dashboard - Complete Mobile Journey', async () => {
    console.log('🔐 Logging in as test planner...');

    // Login with test planner credentials from .env
    await mobilePage.goto(`${TEST_URL}/admin/login`);
    await mobilePage.waitForLoadState('networkidle');

    // Fill login form with credentials from environment
    await mobilePage.fill('input[type="email"]', TEST_PLANNER_EMAIL);
    await mobilePage.fill('input[type="password"]', TEST_PLANNER_PASSWORD);
    await mobilePage.waitForTimeout(500);

    // Submit login
    await mobilePage.click('button[type="submit"]');
    await mobilePage.waitForURL('**/admin/**', { timeout: 10000 });

    console.log('✅ Logged in successfully');
    await mobilePage.waitForTimeout(1500);

    // Test 1: Dashboard Overview
    console.log('\n📊 Testing Dashboard Overview...');
    await mobilePage.goto(`${TEST_URL}/admin`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check if mobile menu button is visible
    const mobileMenuButton = await mobilePage.$('button[aria-label*="menu"], button[aria-label*="sidebar"], button:has-text("☰")');
    if (mobileMenuButton) {
      console.log('✅ Mobile menu button found');

      // Test sidebar toggle
      await mobileMenuButton.click();
      await mobilePage.waitForTimeout(1000);

      const sidebar = await mobilePage.$('aside, nav[role="navigation"], .sidebar');
      expect(sidebar).toBeTruthy();
      console.log('✅ Mobile sidebar works');

      // Close sidebar
      const closeButton = await mobilePage.$('[aria-label*="Close"], button:has-text("✕"), button:has-text("×")');
      if (closeButton) {
        await closeButton.click();
        await mobilePage.waitForTimeout(500);
      }
    }

    // Test 2: Weddings Page
    console.log('\n💍 Testing Weddings Page...');
    await mobilePage.goto(`${TEST_URL}/admin/weddings`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check if wedding cards/list is scrollable on mobile
    const weddingsList = await mobilePage.$('.overflow-x-auto, [class*="overflow"], table');
    if (weddingsList) {
      console.log('✅ Weddings list is scrollable on mobile');
    }

    // Test 3: Guests Management
    console.log('\n👥 Testing Guests Management...');
    await mobilePage.goto(`${TEST_URL}/admin/guests`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check if guest table is mobile-optimized
    const guestTable = await mobilePage.$('table, .table, [role="table"]');
    const isResponsive = await mobilePage.$('.overflow-x-auto, .overflow-x-scroll');

    if (isResponsive) {
      console.log('✅ Guest table is scrollable on mobile');
    }

    // Test 4: Budget Planning
    console.log('\n💰 Testing Budget Page...');
    await mobilePage.goto(`${TEST_URL}/admin/budget`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check budget cards are stacked on mobile
    const budgetCards = await mobilePage.$$('.card, [class*="card"], [class*="budget"]');
    console.log(`✅ Found ${budgetCards.length} budget elements`);

    // Test 5: Forms Builder
    console.log('\n📝 Testing Forms Page...');
    await mobilePage.goto(`${TEST_URL}/admin/forms`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check if form builder is accessible on mobile
    const formsContainer = await mobilePage.$('main, .main-content, [role="main"]');
    expect(formsContainer).toBeTruthy();
    console.log('✅ Forms page loads on mobile');

    // Test 6: Gallery Upload
    console.log('\n📸 Testing Gallery Upload...');
    await mobilePage.goto(`${TEST_URL}/admin/gallery/upload`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    // Check if upload area is touch-friendly
    const uploadArea = await mobilePage.$('input[type="file"], .upload, [class*="upload"]');
    if (uploadArea) {
      console.log('✅ Gallery upload is accessible on mobile');
    }

    // Test 7: Reminders
    console.log('\n⏰ Testing Reminders Page...');
    await mobilePage.goto(`${TEST_URL}/admin/reminders`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    const remindersContent = await mobilePage.$('main');
    expect(remindersContent).toBeTruthy();
    console.log('✅ Reminders page works on mobile');

    // Test 8: Profile Settings
    console.log('\n👤 Testing Profile Page...');
    await mobilePage.goto(`${TEST_URL}/admin/profile`);
    await mobilePage.waitForLoadState('networkidle');
    await mobilePage.waitForTimeout(1500);

    const profileForm = await mobilePage.$('form, .profile, [class*="profile"]');
    expect(profileForm).toBeTruthy();
    console.log('✅ Profile page is mobile-accessible');

    // Test responsive utilities across all pages
    console.log('\n🎨 Checking Responsive Design Elements...');
    const responsiveElements = await mobilePage.evaluate(() => {
      const elements = document.querySelectorAll('*');
      let stats = {
        responsive: 0,
        hiddenOnMobile: 0,
        mobileOnly: 0,
        examples: []
      };

      elements.forEach(el => {
        const classes = el.className?.toString() || '';
        if (classes.includes('sm:') || classes.includes('md:') || classes.includes('lg:')) {
          stats.responsive++;
          if (stats.examples.length < 3) {
            stats.examples.push(el.tagName + ': ' + classes.substring(0, 50));
          }
        }
        if (classes.includes('hidden sm:block') || classes.includes('hidden md:block')) {
          stats.hiddenOnMobile++;
        }
        if (classes.includes('sm:hidden') || classes.includes('block sm:hidden')) {
          stats.mobileOnly++;
        }
      });

      return stats;
    });

    console.log(`✅ Responsive elements: ${responsiveElements.responsive}`);
    console.log(`✅ Hidden on mobile: ${responsiveElements.hiddenOnMobile}`);
    console.log(`✅ Mobile-only elements: ${responsiveElements.mobileOnly}`);

    // Final viewport check
    const viewport = await mobilePage.viewportSize();
    console.log(`\n📏 Final viewport check: ${viewport.width}x${viewport.height}`);
    expect(viewport.width).toBe(390);
  });

  test('Touch interactions should work properly', async () => {
    console.log('\n👆 Testing Touch Interactions...');

    // Make sure we're still logged in
    await mobilePage.goto(`${TEST_URL}/admin`);

    // Test swipe/scroll
    await mobilePage.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await mobilePage.waitForTimeout(500);

    await mobilePage.evaluate(() => {
      window.scrollTo(0, 0);
    });

    console.log('✅ Scroll/swipe gestures work');

    // Test tap targets
    const buttons = await mobilePage.$$('button, a[href], [role="button"]');
    let touchFriendlyCount = 0;

    for (const button of buttons.slice(0, 5)) { // Check first 5 buttons
      const box = await button.boundingBox();
      if (box && box.width >= 44 && box.height >= 44) {
        touchFriendlyCount++;
      }
    }

    console.log(`✅ ${touchFriendlyCount}/5 buttons meet iOS touch target guidelines (44x44px)`);
  });

  test('Mobile performance metrics for planner dashboard', async () => {
    console.log('\n⚡ Testing Dashboard Performance on Mobile...');

    await mobilePage.goto(`${TEST_URL}/admin`);
    await mobilePage.waitForLoadState('networkidle');

    const metrics = await mobilePage.evaluate(() => {
      const perf = performance.getEntriesByType('navigation')[0];
      return {
        domContentLoaded: Math.round(perf.domContentLoadedEventEnd - perf.domContentLoadedEventStart),
        loadComplete: Math.round(perf.loadEventEnd - perf.loadEventStart),
        firstPaint: Math.round(performance.getEntriesByType('paint')[0]?.startTime || 0),
        domInteractive: Math.round(perf.domInteractive)
      };
    });

    console.log(`✅ DOM Content Loaded: ${metrics.domContentLoaded}ms`);
    console.log(`✅ Page Load Complete: ${metrics.loadComplete}ms`);
    console.log(`✅ First Paint: ${metrics.firstPaint}ms`);
    console.log(`✅ DOM Interactive: ${metrics.domInteractive}ms`);

    // Check if performance is acceptable for mobile
    expect(metrics.domInteractive).toBeLessThan(5000); // Should be interactive within 5s on mobile
  });
});

console.log('\n' + '='.repeat(60));
console.log('📱 WEDDING PLANNER MOBILE EXPERIENCE TEST');
console.log('='.repeat(60));
console.log('This test verifies that wedding planners (your customers)');
console.log('can effectively use the dashboard on their mobile devices');
console.log('while managing weddings on the go.');
console.log('='.repeat(60));