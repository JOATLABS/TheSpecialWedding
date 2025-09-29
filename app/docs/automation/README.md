# Automation Attributes Implementation Guide

## Overview

This directory contains comprehensive documentation for the dynamic automation attributes system implemented across the Wedding Web Application SaaS platform.

## Project Scope

**System Type**: Multi-tenant SaaS wedding planning platform
**Components**: 30+ API modules, 30+ services, 20+ admin interfaces
**Users**: ROOT_ADMIN, wedding planners, vendors, guests
**Scale**: Enterprise-grade with subscription management

## Documentation Structure

### Core Documentation
- [`README.md`](./README.md) - This guide
- [`implementation-log.md`](./implementation-log.md) - Detailed change tracking
- [`automation-patterns.md`](./patterns/README.md) - Reusable patterns library

### Component Documentation
- [`components/`](./components/) - Per-component implementation details
- [`patterns/`](./patterns/) - Reusable automation patterns
- [`scripts/`](./scripts/) - Detection and validation tools

## Implementation Philosophy

### Dynamic > Static
```tsx
// ❌ Static (limited)
<button id="delete-button">Delete</button>

// ✅ Dynamic (powerful)
<button
  {...guestAutomationAttrs(guest, 'delete')}
  onClick={() => deleteGuest(guest.id)}
>
  Delete {guest.name}
</button>
```

### Context-Aware Targeting
- **Entity**: What you're interacting with (guest, wedding, form)
- **Action**: What you're doing (create, read, update, delete)
- **Context**: Where you are (admin, public, modal)
- **State**: Current status (loading, valid, error)

## Core Utilities

### Automation Attributes Generator
```typescript
import { createAutomationAttrs } from '@/app/utils/automation-attrs';

// Generate consistent attributes
const attrs = createAutomationAttrs({
  entity: 'guest',
  action: 'delete',
  entityId: guest.id,
  context: 'admin',
  state: loading ? 'loading' : 'ready'
});
```

### Selector Helpers
```typescript
import { automationSelectors as $ } from '@/app/utils/automation-attrs';

// Test targeting
await page.click($.guestAction('123', 'delete'));
await page.waitForSelector($.withState('ready'));
```

## Implementation Status

### ✅ Completed
- Documentation structure
- Core utilities system
- Pattern definitions

### 🚧 In Progress
- Authentication flows
- Guest management
- Form builder system

### 📋 Planned
- Wedding management
- Communication systems
- Subscription flows
- UI component library

## Quick Start

### For Developers
1. Import automation utilities
2. Apply to components using established patterns
3. Document changes in component-specific files
4. Add test examples

### For QA/Testing
1. Use automation selectors for reliable targeting
2. Reference component documentation for available attributes
3. Follow naming patterns for consistency

### For New Components
1. Add automation attributes from the start
2. Follow established naming conventions
3. Document patterns for reuse

## Naming Conventions

### IDs
- **Pattern**: `{entity}-{action}-{entityId?}`
- **Examples**: `guest-delete-123`, `form-submit-contact`

### Data Attributes
- **Entity**: `data-entity="guest"`
- **Action**: `data-action="delete"`
- **Context**: `data-context="admin"`
- **State**: `data-state="loading"`
- **Custom**: `data-{entity}-id="123"`

### Test IDs
- **Pattern**: `data-testid="{entity}-{action}"`
- **Examples**: `data-testid="guest-delete"`, `data-testid="form-submit"`

## Testing Examples

### Playwright
```typescript
// Target specific guest delete
await page.click('[data-guest-id="123"][data-action="delete"]');

// Wait for ready state
await page.waitForSelector('[data-state="ready"]');

// Find all delete actions
const deleteButtons = page.locator('[data-action="delete"]');
```

### Cypress
```typescript
// Semantic targeting
cy.get('[data-entity="guest"][data-action="edit"]').click();

// State-aware interactions
cy.get('[data-form-valid="true"]').should('exist');
```

## Support

### Issues
- Report missing attributes using detection scripts
- Document new patterns in appropriate component files
- Follow naming conventions for consistency

### Contributions
- Update implementation log with all changes
- Add test examples for new patterns
- Maintain documentation quality

---

*Last Updated: $(date)*
*Implementation Status: Foundation Complete, Rolling Out*