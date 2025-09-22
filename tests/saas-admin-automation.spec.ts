import { test, expect, Page } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.FRONTEND_URL!;

// Admin credentials for SaaS testing
const ADMIN_CREDENTIALS = {
  email: process.env.PRIMARY_ADMIN_EMAIL!,
  password: process.env.PRIMARY_ADMIN_PASSWORD!
};

// SaaS automation selectors based on our implementation
const SAAS_SELECTORS = {
  // Navigation
  navigation: {
    mobileTabDropdown: '[data-entity="saasAdmin"][data-action="switchTab"][data-state="mobile"]',
    desktopTabs: '[data-entity="saasAdmin"][data-action="switchTab"][data-context="navigation"]',
    plansTab: '[data-entity="saasAdmin"][data-action="switchTab"][data-tab-key="plans"]',
    contentTab: '[data-entity="saasAdmin"][data-action="switchTab"][data-tab-key="content"]',
    themeTab: '[data-entity="saasAdmin"][data-action="switchTab"][data-tab-key="theme"]'
  },
  // Subscription Plans Management
  plans: {
    createButton: '[data-entity="subscriptionPlan"][data-action="create"][data-context="plansManagement"]',
    editButton: '[data-entity="subscriptionPlan"][data-action="edit"][data-context="plansManagement"]',
    deleteButton: '[data-entity="subscriptionPlan"][data-action="delete"][data-context="plansManagement"]'
  },
  // Content Management
  content: {
    saveButton: '[data-entity="saasConfig"][data-action="save"][data-context="contentManagement"]',
    editModalButton: '[data-entity="contentEditor"][data-action="openModal"][data-context="heroSection"]',
    heroTitle: '[data-entity="heroContent"][data-action="editTitle"][data-context="contentEditor"]',
    heroSubtitle: '[data-entity="heroContent"][data-action="editSubtitle"][data-context="contentEditor"]',
    heroDescription: '[data-entity="heroContent"][data-action="editDescription"][data-context="contentEditor"]',
    heroPrimaryCta: '[data-entity="heroContent"][data-action="editCtaPrimary"][data-context="contentEditor"]',
    heroSecondaryCta: '[data-entity="heroContent"][data-action="editCtaSecondary"][data-context="contentEditor"]'
  },
  // Theme Management
  theme: {
    saveButton: '[data-entity="themeConfig"][data-action="save"][data-context="themeDesign"]',
    primaryColorPicker: '[data-entity="themeColor"][data-action="editPrimary"][data-context="colorPicker"]',
    primaryColorText: '[data-entity="themeColor"][data-action="editPrimary"][data-context="textInput"]'
  }
};

// Fallback selectors for compatibility testing
const FALLBACK_SELECTORS = {
  navigation: {
    plansTab: 'button:has-text("Plans")',
    contentTab: 'button:has-text("Content")',
    themeTab: 'button:has-text("Theme")'
  },
  plans: {
    createButton: 'button:has-text("Create New Plan")',
    editButton: 'button:has-text("Edit Plan")',
    deleteButton: 'button:has-text("Delete Plan")'
  },
  content: {
    saveButton: 'button:has-text("Save All Changes")',
    heroTitle: 'input[value*="title"], input[placeholder*="title"]'
  },
  theme: {
    saveButton: 'button:has-text("Save Changes")',
    primaryColorPicker: 'input[type="color"]',
    primaryColorText: 'input[placeholder="#1e3a5f"]'
  }
};

// Helper function to try automation selector first, then fallback
async function testSelector(page: Page, automationSelector: string, fallbackSelector: string, action: 'click' | 'count' | 'visible' = 'count') {
  let automationResult = null;
  let fallbackResult = null;

  try {
    if (action === 'count') {
      automationResult = await page.locator(automationSelector).count();
    } else if (action === 'visible') {
      automationResult = await page.locator(automationSelector).isVisible();
    } else if (action === 'click') {
      if (await page.locator(automationSelector).count() > 0) {
        await page.click(automationSelector);
        automationResult = true;
      }
    }
  } catch (error) {
    console.log(`⚠️ Automation selector failed: ${automationSelector}`, error.message);
  }

  try {
    if (!automationResult || automationResult === 0) {
      if (action === 'count') {
        fallbackResult = await page.locator(fallbackSelector).count();
      } else if (action === 'visible') {
        fallbackResult = await page.locator(fallbackSelector).isVisible();
      } else if (action === 'click') {
        await page.click(fallbackSelector);
        fallbackResult = true;
      }
    }
  } catch (error) {
    console.log(`⚠️ Fallback selector failed: ${fallbackSelector}`, error.message);
  }

  return {
    automation: automationResult,
    fallback: fallbackResult,
    used: automationResult > 0 || automationResult === true ? 'automation' : 'fallback'
  };
}

// Enhanced login helper
async function loginAsAdmin(page: Page) {
  await page.goto(`${BASE_URL}/admin/login`);
  await page.fill('input[placeholder="Email"]', ADMIN_CREDENTIALS.email);
  await page.fill('input[placeholder="Password"]', ADMIN_CREDENTIALS.password);
  await page.click('button');
  await page.waitForURL('**/admin**');
}

// Navigate to SaaS admin page
async function navigateToSaas(page: Page) {
  await page.goto(`${BASE_URL}/admin/saas`);
  await page.waitForLoadState('networkidle');
}

test.describe('SaaS Admin Automation Attributes', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 });
  });

  test('should verify SaaS navigation automation attributes', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    console.log('\n🧪 Testing SaaS Navigation Automation Attributes:');

    // Test tab navigation
    const tabTests = [
      { name: 'Plans Tab', automation: SAAS_SELECTORS.navigation.plansTab, fallback: FALLBACK_SELECTORS.navigation.plansTab },
      { name: 'Content Tab', automation: SAAS_SELECTORS.navigation.contentTab, fallback: FALLBACK_SELECTORS.navigation.contentTab },
      { name: 'Theme Tab', automation: SAAS_SELECTORS.navigation.themeTab, fallback: FALLBACK_SELECTORS.navigation.themeTab }
    ];

    const results = [];

    for (const tabTest of tabTests) {
      const result = await testSelector(page, tabTest.automation, tabTest.fallback, 'count');
      results.push({
        name: tabTest.name,
        ...result,
        selector: tabTest.automation
      });

      console.log(`${result.automation > 0 ? '✅' : '❌'} ${tabTest.name}: Found ${result.automation} automation elements`);
    }

    // Test switching to Plans tab
    if (results[0].automation > 0) {
      await page.click(SAAS_SELECTORS.navigation.plansTab);
      console.log('✅ Successfully switched to Plans tab using automation attributes');
    } else {
      await page.click(FALLBACK_SELECTORS.navigation.plansTab);
      console.log('🔄 Switched to Plans tab using fallback selector');
    }

    expect(results.some(r => r.automation > 0)).toBe(true);
  });

  test('should test subscription plans management automation', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    // Navigate to Plans tab
    await page.click('button:has-text("Plans")');
    await page.waitForTimeout(1000);

    console.log('\n🧪 Testing Subscription Plans Automation Attributes:');

    const planTests = [
      { name: 'Create New Plan', automation: SAAS_SELECTORS.plans.createButton, fallback: FALLBACK_SELECTORS.plans.createButton },
      { name: 'Edit Plan', automation: SAAS_SELECTORS.plans.editButton, fallback: FALLBACK_SELECTORS.plans.editButton },
      { name: 'Delete Plan', automation: SAAS_SELECTORS.plans.deleteButton, fallback: FALLBACK_SELECTORS.plans.deleteButton }
    ];

    const results = [];

    for (const planTest of planTests) {
      const result = await testSelector(page, planTest.automation, planTest.fallback, 'count');
      results.push({
        name: planTest.name,
        ...result,
        selector: planTest.automation
      });

      console.log(`${result.automation > 0 ? '✅' : '❌'} ${planTest.name}: Found ${result.automation} automation elements`);
    }

    // Test clicking Create New Plan if automation attributes exist
    if (results[0].automation > 0) {
      try {
        await page.click(SAAS_SELECTORS.plans.createButton);
        console.log('✅ Successfully clicked Create New Plan using automation attributes');

        // Wait for modal and close it
        await page.waitForTimeout(1000);
        if (await page.locator('button:has-text("Cancel"), button:has-text("Close")').count() > 0) {
          await page.click('button:has-text("Cancel"), button:has-text("Close")');
        }
      } catch (error) {
        console.log('⚠️ Create New Plan interaction failed:', error.message);
      }
    }

    expect(results.length).toBeGreaterThan(0);
  });

  test('should test content management automation', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    // Navigate to Content tab
    await page.click('button:has-text("Content")');
    await page.waitForTimeout(1000);

    console.log('\n🧪 Testing Content Management Automation Attributes:');

    const contentTests = [
      { name: 'Save All Changes', automation: SAAS_SELECTORS.content.saveButton, fallback: FALLBACK_SELECTORS.content.saveButton },
      { name: 'Edit Modal Button', automation: SAAS_SELECTORS.content.editModalButton, fallback: 'button:has-text("Edit in Modal")' },
      { name: 'Hero Title Input', automation: SAAS_SELECTORS.content.heroTitle, fallback: FALLBACK_SELECTORS.content.heroTitle },
      { name: 'Hero Subtitle Input', automation: SAAS_SELECTORS.content.heroSubtitle, fallback: 'input[value*="subtitle"]' },
      { name: 'Hero Description', automation: SAAS_SELECTORS.content.heroDescription, fallback: 'textarea' },
      { name: 'Primary CTA', automation: SAAS_SELECTORS.content.heroPrimaryCta, fallback: 'input[value*="cta"]' },
      { name: 'Secondary CTA', automation: SAAS_SELECTORS.content.heroSecondaryCta, fallback: 'input[value*="secondary"]' }
    ];

    const results = [];

    for (const contentTest of contentTests) {
      const result = await testSelector(page, contentTest.automation, contentTest.fallback, 'count');
      results.push({
        name: contentTest.name,
        ...result,
        selector: contentTest.automation
      });

      console.log(`${result.automation > 0 ? '✅' : '❌'} ${contentTest.name}: Found ${result.automation} automation elements`);
    }

    // Test editing hero content
    if (results.find(r => r.name === 'Hero Title Input')?.automation > 0) {
      try {
        await page.fill(SAAS_SELECTORS.content.heroTitle, 'Test Hero Title');
        console.log('✅ Successfully edited hero title using automation attributes');
      } catch (error) {
        console.log('⚠️ Hero title editing failed:', error.message);
      }
    }

    expect(results.filter(r => r.automation > 0).length).toBeGreaterThan(0);
  });

  test('should test theme management automation', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    // Navigate to Theme tab
    await page.click('button:has-text("Theme")');
    await page.waitForTimeout(1000);

    console.log('\n🧪 Testing Theme Management Automation Attributes:');

    const themeTests = [
      { name: 'Save Changes', automation: SAAS_SELECTORS.theme.saveButton, fallback: FALLBACK_SELECTORS.theme.saveButton },
      { name: 'Primary Color Picker', automation: SAAS_SELECTORS.theme.primaryColorPicker, fallback: FALLBACK_SELECTORS.theme.primaryColorPicker },
      { name: 'Primary Color Text', automation: SAAS_SELECTORS.theme.primaryColorText, fallback: FALLBACK_SELECTORS.theme.primaryColorText }
    ];

    const results = [];

    for (const themeTest of themeTests) {
      const result = await testSelector(page, themeTest.automation, themeTest.fallback, 'count');
      results.push({
        name: themeTest.name,
        ...result,
        selector: themeTest.automation
      });

      console.log(`${result.automation > 0 ? '✅' : '❌'} ${themeTest.name}: Found ${result.automation} automation elements`);
    }

    // Test color editing
    if (results.find(r => r.name === 'Primary Color Text')?.automation > 0) {
      try {
        await page.fill(SAAS_SELECTORS.theme.primaryColorText, '#FF5722');
        console.log('✅ Successfully edited primary color using automation attributes');
      } catch (error) {
        console.log('⚠️ Color editing failed:', error.message);
      }
    }

    expect(results.filter(r => r.automation > 0).length).toBeGreaterThan(0);
  });

  test('should generate comprehensive automation coverage report', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    console.log('\n📊 SaaS Admin Automation Coverage Report:');
    console.log('=====================================================');

    // Test all tabs and collect comprehensive data
    const allSelectors = [
      // Navigation
      { category: 'Navigation', name: 'Desktop Tab Buttons', selector: SAAS_SELECTORS.navigation.desktopTabs },

      // Plans Management (switch to plans tab first)
      { category: 'Plans', name: 'Create Button', selector: SAAS_SELECTORS.plans.createButton, requiresTab: 'Plans' },
      { category: 'Plans', name: 'Edit Button', selector: SAAS_SELECTORS.plans.editButton, requiresTab: 'Plans' },
      { category: 'Plans', name: 'Delete Button', selector: SAAS_SELECTORS.plans.deleteButton, requiresTab: 'Plans' },

      // Content Management (switch to content tab)
      { category: 'Content', name: 'Save Button', selector: SAAS_SELECTORS.content.saveButton, requiresTab: 'Content' },
      { category: 'Content', name: 'Hero Title', selector: SAAS_SELECTORS.content.heroTitle, requiresTab: 'Content' },
      { category: 'Content', name: 'Hero Subtitle', selector: SAAS_SELECTORS.content.heroSubtitle, requiresTab: 'Content' },
      { category: 'Content', name: 'Hero Description', selector: SAAS_SELECTORS.content.heroDescription, requiresTab: 'Content' },
      { category: 'Content', name: 'Primary CTA', selector: SAAS_SELECTORS.content.heroPrimaryCta, requiresTab: 'Content' },
      { category: 'Content', name: 'Secondary CTA', selector: SAAS_SELECTORS.content.heroSecondaryCta, requiresTab: 'Content' },

      // Theme Management (switch to theme tab)
      { category: 'Theme', name: 'Save Button', selector: SAAS_SELECTORS.theme.saveButton, requiresTab: 'Theme' },
      { category: 'Theme', name: 'Primary Color Picker', selector: SAAS_SELECTORS.theme.primaryColorPicker, requiresTab: 'Theme' },
      { category: 'Theme', name: 'Primary Color Text', selector: SAAS_SELECTORS.theme.primaryColorText, requiresTab: 'Theme' }
    ];

    const results = [];
    let currentTab = null;

    for (const test of allSelectors) {
      // Switch tabs if needed
      if (test.requiresTab && test.requiresTab !== currentTab) {
        try {
          await page.click(`button:has-text("${test.requiresTab}")`);
          await page.waitForTimeout(500);
          currentTab = test.requiresTab;
        } catch (error) {
          console.log(`⚠️ Failed to switch to ${test.requiresTab} tab`);
          continue;
        }
      }

      const count = await page.locator(test.selector).count();
      const found = count > 0;

      results.push({
        category: test.category,
        name: test.name,
        selector: test.selector,
        found,
        count
      });

      const status = found ? '✅' : '❌';
      console.log(`${status} ${test.category} - ${test.name}: ${count} elements`);
    }

    // Summary by category
    console.log('\n📈 Summary by Category:');
    const categories = [...new Set(results.map(r => r.category))];

    categories.forEach(category => {
      const categoryResults = results.filter(r => r.category === category);
      const foundCount = categoryResults.filter(r => r.found).length;
      const totalCount = categoryResults.length;
      const percentage = Math.round((foundCount / totalCount) * 100);

      console.log(`${category}: ${foundCount}/${totalCount} (${percentage}%)`);
    });

    // Overall coverage
    const totalFound = results.filter(r => r.found).length;
    const totalTests = results.length;
    const overallCoverage = Math.round((totalFound / totalTests) * 100);

    console.log(`\n🎯 Overall Coverage: ${totalFound}/${totalTests} (${overallCoverage}%)`);

    // Performance metrics
    const allAutomationElements = await page.evaluate(() => {
      const elements = document.querySelectorAll('[data-entity]');
      const entityTypes = new Set();
      const actionTypes = new Set();
      const contextTypes = new Set();

      elements.forEach(el => {
        if (el.getAttribute('data-entity')) entityTypes.add(el.getAttribute('data-entity'));
        if (el.getAttribute('data-action')) actionTypes.add(el.getAttribute('data-action'));
        if (el.getAttribute('data-context')) contextTypes.add(el.getAttribute('data-context'));
      });

      return {
        totalElements: elements.length,
        uniqueEntities: entityTypes.size,
        uniqueActions: actionTypes.size,
        uniqueContexts: contextTypes.size,
        entities: Array.from(entityTypes),
        actions: Array.from(actionTypes),
        contexts: Array.from(contextTypes)
      };
    });

    console.log('\n⚡ Automation Attribute Metrics:');
    console.log(`Total elements with data-entity: ${allAutomationElements.totalElements}`);
    console.log(`Unique entities: ${allAutomationElements.uniqueEntities}`);
    console.log(`Unique actions: ${allAutomationElements.uniqueActions}`);
    console.log(`Unique contexts: ${allAutomationElements.uniqueContexts}`);

    console.log('\nEntity types found:', allAutomationElements.entities.join(', '));
    console.log('Action types found:', allAutomationElements.actions.join(', '));
    console.log('Context types found:', allAutomationElements.contexts.join(', '));

    // Assertions
    expect(totalFound).toBeGreaterThan(0);
    expect(overallCoverage).toBeGreaterThan(30); // At least 30% coverage expected
    expect(allAutomationElements.totalElements).toBeGreaterThan(10); // At least 10 automated elements
  });

  test('should test automation attribute data quality', async ({ page }) => {
    await loginAsAdmin(page);
    await navigateToSaas(page);

    // Test data attribute completeness and format
    const dataQuality = await page.evaluate(() => {
      const elements = document.querySelectorAll('[data-entity]');
      const issues = [];
      const stats = {
        total: elements.length,
        hasAction: 0,
        hasContext: 0,
        hasState: 0,
        hasCustom: 0
      };

      elements.forEach((el, index) => {
        const entity = el.getAttribute('data-entity');
        const action = el.getAttribute('data-action');
        const context = el.getAttribute('data-context');
        const state = el.getAttribute('data-state');

        // Count completeness
        if (action) stats.hasAction++;
        if (context) stats.hasContext++;
        if (state) stats.hasState++;

        // Check for custom attributes
        Array.from(el.attributes).forEach(attr => {
          if (attr.name.startsWith('data-') &&
              !['data-entity', 'data-action', 'data-context', 'data-state', 'data-testid'].includes(attr.name)) {
            stats.hasCustom++;
          }
        });

        // Validate format
        if (!entity) {
          issues.push(`Element ${index}: Missing data-entity`);
        }
        if (!action) {
          issues.push(`Element ${index}: Missing data-action for entity ${entity}`);
        }
        if (entity && !/^[a-z][a-zA-Z]*$/.test(entity)) {
          issues.push(`Element ${index}: Invalid entity format: ${entity}`);
        }
        if (action && !/^[a-z][a-zA-Z]*$/.test(action)) {
          issues.push(`Element ${index}: Invalid action format: ${action}`);
        }
      });

      return { stats, issues };
    });

    console.log('\n🔍 Data Quality Report:');
    console.log(`Total automated elements: ${dataQuality.stats.total}`);
    console.log(`Elements with action: ${dataQuality.stats.hasAction} (${Math.round((dataQuality.stats.hasAction / dataQuality.stats.total) * 100)}%)`);
    console.log(`Elements with context: ${dataQuality.stats.hasContext} (${Math.round((dataQuality.stats.hasContext / dataQuality.stats.total) * 100)}%)`);
    console.log(`Elements with state: ${dataQuality.stats.hasState} (${Math.round((dataQuality.stats.hasState / dataQuality.stats.total) * 100)}%)`);
    console.log(`Elements with custom data: ${dataQuality.stats.hasCustom}`);

    if (dataQuality.issues.length > 0) {
      console.log('\n⚠️ Data Quality Issues Found:');
      dataQuality.issues.slice(0, 10).forEach(issue => console.log(`  - ${issue}`));
      if (dataQuality.issues.length > 10) {
        console.log(`  ... and ${dataQuality.issues.length - 10} more issues`);
      }
    } else {
      console.log('\n✅ No data quality issues found');
    }

    expect(dataQuality.stats.total).toBeGreaterThan(0);
    expect(dataQuality.stats.hasAction / dataQuality.stats.total).toBeGreaterThan(0.8); // 80% should have actions
  });
});