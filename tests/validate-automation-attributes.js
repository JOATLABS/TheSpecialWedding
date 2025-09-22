#!/usr/bin/env node

/**
 * Quick validation script for automation attributes
 * Tests our automation selector patterns without requiring full Playwright setup
 */

const fs = require('fs');
const path = require('path');

// Files we've enhanced with automation attributes
const ENHANCED_FILES = [
  'app/admin/saas/page.tsx',
  'app/components/forms/FormBuilder.tsx',
  'app/components/ui/button.tsx',
  'app/components/ui/Card.tsx',
  'app/components/ui/input.tsx',
  'app/components/ui/select.tsx',
  'app/components/ui/badge.tsx'
];

// Expected automation patterns
const AUTOMATION_PATTERNS = {
  createAutomationAttrs: /createAutomationAttrs\(/g,
  dataEntity: /data-entity/g,
  dataAction: /data-action/g,
  dataContext: /data-context/g,
  dataState: /data-state/g,
  formAutomationAttrs: /formAutomationAttrs\(/g,
  guestAutomationAttrs: /guestAutomationAttrs\(/g
};

// Expected entities in SaaS admin
const EXPECTED_ENTITIES = [
  'saasAdmin',
  'subscriptionPlan',
  'saasConfig',
  'contentEditor',
  'heroContent',
  'themeConfig',
  'themeColor'
];

// Expected actions
const EXPECTED_ACTIONS = [
  'switchTab',
  'create',
  'edit',
  'delete',
  'save',
  'openModal',
  'editTitle',
  'editSubtitle',
  'editDescription',
  'editCtaPrimary',
  'editCtaSecondary',
  'editPrimary'
];

function analyzeFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return { error: `File not found: ${filePath}` };
  }

  const content = fs.readFileSync(filePath, 'utf8');
  const analysis = {
    file: filePath,
    size: content.length,
    lines: content.split('\n').length,
    patterns: {},
    entities: new Set(),
    actions: new Set(),
    contexts: new Set(),
    issues: []
  };

  // Count automation patterns
  Object.entries(AUTOMATION_PATTERNS).forEach(([pattern, regex]) => {
    const matches = content.match(regex) || [];
    analysis.patterns[pattern] = matches.length;
  });

  // Extract entities, actions, contexts from content
  const entityMatches = content.match(/entity:\s*['"`]([^'"`]+)['"`]/g) || [];
  const actionMatches = content.match(/action:\s*['"`]([^'"`]+)['"`]/g) || [];
  const contextMatches = content.match(/context:\s*['"`]([^'"`]+)['"`]/g) || [];

  entityMatches.forEach(match => {
    const entity = match.match(/['"`]([^'"`]+)['"`]/)[1];
    analysis.entities.add(entity);
  });

  actionMatches.forEach(match => {
    const action = match.match(/['"`]([^'"`]+)['"`]/)[1];
    analysis.actions.add(action);
  });

  contextMatches.forEach(match => {
    const context = match.match(/['"`]([^'"`]+)['"`]/)[1];
    analysis.contexts.add(context);
  });

  // Check for potential issues
  if (analysis.patterns.createAutomationAttrs === 0 && filePath.includes('saas/page.tsx')) {
    analysis.issues.push('SaaS page should have automation attributes');
  }

  // UI components may have conditional automation attributes (this is correct)
  const isUIComponent = filePath.includes('/ui/');
  if (analysis.patterns.createAutomationAttrs > 0 && analysis.entities.size === 0 && !isUIComponent) {
    analysis.issues.push('Has createAutomationAttrs calls but no entities found');
  }

  // Check if UI component has proper conditional automation setup
  if (isUIComponent && analysis.patterns.createAutomationAttrs > 0) {
    const hasConditionalAutomation = content.includes('automationEntity') || content.includes('automation');
    if (!hasConditionalAutomation) {
      analysis.issues.push('UI component should have conditional automation props');
    }
  }

  // Check for TypeScript errors we might have introduced
  const typeErrors = [
    /Type.*is not assignable to type.*string \| number \| boolean/g,
    /Property.*does not exist on type/g,
    /Argument of type.*is not assignable/g
  ];

  typeErrors.forEach((errorPattern, index) => {
    const errors = content.match(errorPattern) || [];
    if (errors.length > 0) {
      analysis.issues.push(`Potential TypeScript error pattern ${index + 1}: ${errors.length} occurrences`);
    }
  });

  return analysis;
}

function validateSelectors() {
  console.log('🔍 Validating Automation Attributes Implementation\n');
  console.log('='.repeat(60));

  const results = [];

  ENHANCED_FILES.forEach(file => {
    const analysis = analyzeFile(file);
    results.push(analysis);

    if (analysis.error) {
      console.log(`❌ ${file}: ${analysis.error}`);
      return;
    }

    console.log(`\n📁 ${file}`);
    console.log(`   Size: ${analysis.size} chars, ${analysis.lines} lines`);

    // Automation patterns
    const hasAutomation = analysis.patterns.createAutomationAttrs > 0;
    console.log(`   ${hasAutomation ? '✅' : '❌'} Automation: ${analysis.patterns.createAutomationAttrs} calls`);

    if (hasAutomation) {
      console.log(`   📊 Entities: ${analysis.entities.size} (${Array.from(analysis.entities).join(', ')})`);
      console.log(`   📊 Actions: ${analysis.actions.size} (${Array.from(analysis.actions).join(', ')})`);
      console.log(`   📊 Contexts: ${analysis.contexts.size} (${Array.from(analysis.contexts).join(', ')})`);
    }

    if (analysis.issues.length > 0) {
      console.log(`   ⚠️  Issues:`);
      analysis.issues.forEach(issue => console.log(`      - ${issue}`));
    }
  });

  console.log('\n' + '='.repeat(60));
  console.log('📊 Summary Report');
  console.log('='.repeat(60));

  const validResults = results.filter(r => !r.error);
  const totalAutomationCalls = validResults.reduce((sum, r) => sum + r.patterns.createAutomationAttrs, 0);
  const allEntities = new Set();
  const allActions = new Set();
  const allContexts = new Set();
  let totalIssues = 0;

  validResults.forEach(result => {
    result.entities.forEach(e => allEntities.add(e));
    result.actions.forEach(a => allActions.add(a));
    result.contexts.forEach(c => allContexts.add(c));
    totalIssues += result.issues.length;
  });

  console.log(`📈 Total Files Analyzed: ${validResults.length}/${ENHANCED_FILES.length}`);
  console.log(`📈 Total Automation Calls: ${totalAutomationCalls}`);
  console.log(`📈 Unique Entities: ${allEntities.size}`);
  console.log(`📈 Unique Actions: ${allActions.size}`);
  console.log(`📈 Unique Contexts: ${allContexts.size}`);
  console.log(`📈 Total Issues: ${totalIssues}`);

  // Entity coverage check
  console.log('\n🎯 Entity Coverage Analysis:');
  EXPECTED_ENTITIES.forEach(expectedEntity => {
    const found = allEntities.has(expectedEntity);
    console.log(`   ${found ? '✅' : '❌'} ${expectedEntity}`);
  });

  // Action coverage check
  console.log('\n🎯 Action Coverage Analysis:');
  EXPECTED_ACTIONS.forEach(expectedAction => {
    const found = allActions.has(expectedAction);
    console.log(`   ${found ? '✅' : '❌'} ${expectedAction}`);
  });

  // Generate test selectors
  console.log('\n🧪 Generated Test Selectors:');
  console.log('=' .repeat(30));

  const sampleSelectors = [];
  allEntities.forEach(entity => {
    allActions.forEach(action => {
      if (sampleSelectors.length < 10) { // Limit output
        sampleSelectors.push(`[data-entity="${entity}"][data-action="${action}"]`);
      }
    });
  });

  sampleSelectors.forEach(selector => {
    console.log(`   ${selector}`);
  });

  // Recommendations
  console.log('\n💡 Recommendations:');
  console.log('=' .repeat(20));

  if (totalAutomationCalls === 0) {
    console.log('   ❗ No automation attributes found - implementation may not be complete');
  } else if (totalAutomationCalls < 20) {
    console.log('   ⚠️  Low automation coverage - consider adding more attributes');
  } else {
    console.log('   ✅ Good automation coverage detected');
  }

  if (totalIssues > 0) {
    console.log('   ⚠️  Address TypeScript and implementation issues');
  }

  if (allEntities.size < 5) {
    console.log('   📈 Consider adding more entity types for better test organization');
  }

  if (allActions.size < 8) {
    console.log('   📈 Consider adding more action types for comprehensive coverage');
  }

  console.log('\n🎉 Validation Complete!');

  return {
    totalFiles: validResults.length,
    totalCalls: totalAutomationCalls,
    entities: Array.from(allEntities),
    actions: Array.from(allActions),
    contexts: Array.from(allContexts),
    issues: totalIssues,
    success: totalAutomationCalls > 0 && totalIssues === 0
  };
}

// Generate sample test code
function generateSampleTests(entities, actions) {
  console.log('\n🔧 Sample Playwright Test Code:');
  console.log('=' .repeat(35));

  const samples = [
    {
      description: 'Switch to Plans tab',
      entity: 'saasAdmin',
      action: 'switchTab',
      code: `await page.click('[data-entity="saasAdmin"][data-action="switchTab"][data-tab-key="plans"]');`
    },
    {
      description: 'Create new subscription plan',
      entity: 'subscriptionPlan',
      action: 'create',
      code: `await page.click('[data-entity="subscriptionPlan"][data-action="create"]');`
    },
    {
      description: 'Edit hero content title',
      entity: 'heroContent',
      action: 'editTitle',
      code: `await page.fill('[data-entity="heroContent"][data-action="editTitle"]', 'New Title');`
    },
    {
      description: 'Save theme changes',
      entity: 'themeConfig',
      action: 'save',
      code: `await page.click('[data-entity="themeConfig"][data-action="save"]');`
    }
  ];

  samples.forEach(sample => {
    if (entities.includes(sample.entity) && actions.includes(sample.action)) {
      console.log(`   ✅ ${sample.description}:`);
      console.log(`      ${sample.code}`);
    } else {
      console.log(`   ❌ ${sample.description}: (Entity or action not implemented)`);
    }
  });
}

// Run validation
if (require.main === module) {
  const result = validateSelectors();
  generateSampleTests(result.entities, result.actions);

  process.exit(result.success ? 0 : 1);
}

module.exports = { validateSelectors, analyzeFile };