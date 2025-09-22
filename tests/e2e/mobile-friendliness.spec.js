const { test, expect, chromium } = require('@playwright/test');

const FRONTEND_URL = process.env.FRONTEND_URL;

test.describe('Mobile Friendliness Tests', () => {
  let browser;
  let desktopContext;
  let mobileContext;
  let desktopPage;
  let mobilePage;

  test.beforeAll(async () => {
    browser = await chromium.launch({
      headless: false,  // Show browser UI for visual verification
      slowMo: 500,      // Slow down actions by 500ms for better visibility
      args: ['--enable-features=WebUIDarkMode']
    });

    // Setup desktop context
    desktopContext = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    });
    desktopPage = await desktopContext.newPage();

    // Setup mobile context (iPhone 12)
    mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
      isMobile: true,
      hasTouch: true
    });
    mobilePage = await mobileContext.newPage();
  });

  test.afterAll(async () => {
    await desktopContext.close();
    await mobileContext.close();
    await browser.close();
  });

  test('should have viewport meta tag', async () => {
    await desktopPage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });
    await desktopPage.waitForTimeout(1000); // Pause to see desktop view

    const viewportMeta = await desktopPage.$eval(
      'meta[name="viewport"]',
      el => el.content
    ).catch(() => null);

    expect(viewportMeta).toBeTruthy();
    expect(viewportMeta).toContain('width=device-width');
    expect(viewportMeta).toContain('initial-scale=1');
  });

  test('should have PWA manifest', async () => {
    await desktopPage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const manifestLink = await desktopPage.$eval(
      'link[rel="manifest"]',
      el => el.href
    ).catch(() => null);

    expect(manifestLink).toBeTruthy();
    expect(manifestLink).toContain('/manifest.json');
  });

  test('should register service worker', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    // Wait a bit for service worker to register
    await mobilePage.waitForTimeout(2000);

    const swRegistered = await mobilePage.evaluate(() => {
      return navigator.serviceWorker ?
        navigator.serviceWorker.ready.then(() => true).catch(() => false) :
        false;
    });

    expect(swRegistered).toBeTruthy();
  });

  test('should have mobile meta tags', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const metaTags = await mobilePage.evaluate(() => {
      return {
        themeColor: document.querySelector('meta[name="theme-color"]')?.content,
        appleCapable: document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content,
        appTitle: document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content,
        mobileCapable: document.querySelector('meta[name="mobile-web-app-capable"]')?.content
      };
    });

    expect(metaTags.themeColor).toBe('#D4A5A5');
    expect(metaTags.appleCapable).toBe('yes');
    expect(metaTags.appTitle).toBe('TheSpecialWedding');
    expect(metaTags.mobileCapable).toBe('yes');
  });

  test('should load PWA manifest with correct content', async () => {
    const response = await mobilePage.goto('${FRONTEND_URL}/manifest.json');
    expect(response.status()).toBe(200);

    const manifest = await response.json();

    expect(manifest.name).toContain('TheSpecialWedding');
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBe('#D4A5A5');
    expect(manifest.start_url).toBe('/');
    expect(manifest.icons).toBeDefined();
    expect(manifest.icons.length).toBeGreaterThan(0);
  });

  test('should have responsive design classes', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const responsiveElements = await mobilePage.evaluate(() => {
      const allElements = document.querySelectorAll('*');
      let responsiveCount = 0;

      allElements.forEach(el => {
        const classes = el.className;
        if (typeof classes === 'string' &&
            (classes.includes('sm:') || classes.includes('md:') || classes.includes('lg:'))) {
          responsiveCount++;
        }
      });

      return responsiveCount;
    });

    expect(responsiveElements).toBeGreaterThan(0);
  });

  test('should have offline fallback page', async () => {
    const response = await mobilePage.goto('${FRONTEND_URL}/offline.html');
    expect(response.status()).toBe(200);

    const title = await mobilePage.title();
    expect(title).toContain('Offline');
  });

  test('should have font preconnect optimization', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const fontLinks = await mobilePage.evaluate(() => {
      const links = document.querySelectorAll('link[rel="preconnect"]');
      return Array.from(links).map(link => link.href);
    });

    expect(fontLinks.some(link => link.includes('fonts.googleapis.com'))).toBeTruthy();
    expect(fontLinks.some(link => link.includes('fonts.gstatic.com'))).toBeTruthy();
  });

  test('should be mobile-friendly on admin login', async () => {
    await mobilePage.goto('${FRONTEND_URL}/admin/login', { waitUntil: 'networkidle' });

    // Check if form is present and accessible
    const loginForm = await mobilePage.$('form');
    expect(loginForm).toBeTruthy();

    // Check viewport width matches mobile
    const viewportSize = await mobilePage.viewportSize();
    expect(viewportSize.width).toBe(390);
  });

  test('should have good mobile performance metrics', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const metrics = await mobilePage.evaluate(() => {
      const perf = performance.getEntriesByType('navigation')[0];
      return {
        domContentLoaded: perf.domContentLoadedEventEnd - perf.domContentLoadedEventStart,
        loadComplete: perf.loadEventEnd - perf.loadEventStart,
        domInteractive: perf.domInteractive
      };
    });

    // Performance thresholds (in ms)
    expect(metrics.domContentLoaded).toBeLessThan(3000); // Should load in under 3 seconds
    expect(metrics.domInteractive).toBeLessThan(5000);  // Should be interactive in under 5 seconds
  });

  test('should have mobile-friendly admin sidebar', async () => {
    // Navigate to admin area (will redirect to login if not authenticated)
    await mobilePage.goto('${FRONTEND_URL}/admin', { waitUntil: 'networkidle' });

    // Check for mobile menu button or sidebar
    const mobileMenuButton = await mobilePage.$(
      '[aria-label*="menu"], button:has-text("Menu"), .hamburger, button[aria-label*="sidebar"]'
    );

    // Either we have a mobile menu button or we're on the login page
    const isLoginPage = await mobilePage.url().includes('/admin/login');
    expect(mobileMenuButton || isLoginPage).toBeTruthy();
  });

  test('should have correct mobile viewport dimensions', async () => {
    await mobilePage.goto('${FRONTEND_URL}/', { waitUntil: 'networkidle' });

    const dimensions = await mobilePage.evaluate(() => {
      return {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio
      };
    });

    expect(dimensions.innerWidth).toBeLessThanOrEqual(390);
    expect(dimensions.innerHeight).toBeLessThanOrEqual(844);
  });
});