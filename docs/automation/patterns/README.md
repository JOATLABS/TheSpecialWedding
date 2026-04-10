# Automation Patterns Library

## Multi-Tenant SaaS Platform Patterns

This library contains reusable automation patterns for the Wedding Web Application SaaS platform.

## Core Entity Patterns

### Guest Management Pattern
```tsx
import { guestAutomationAttrs } from '@/app/utils/automation-attrs';

// Guest actions in admin context
<button
  {...guestAutomationAttrs(guest, 'delete')}
  onClick={() => deleteGuest(guest.id)}
>
  Delete {guest.name}
</button>

// Generates:
// id="guest-delete-123"
// data-testid="guest-delete"
// data-entity="guest"
// data-action="delete"
// data-context="admin"
// data-guest-id="123"
// data-guest-name="john-doe"
```

### Wedding Management Pattern
```tsx
import { weddingAutomationAttrs } from '@/app/utils/automation-attrs';

// Wedding configuration actions
<button
  {...weddingAutomationAttrs(wedding, 'edit')}
  onClick={() => editWedding(wedding.id)}
>
  Edit {wedding.couple_names}
</button>

// Generates:
// id="wedding-edit-456"
// data-testid="wedding-edit"
// data-entity="wedding"
// data-action="edit"
// data-context="admin"
// data-wedding-id="456"
// data-wedding-names="john-jane"
```

### Authentication Pattern
```tsx
import { authAutomationAttrs } from '@/app/utils/automation-attrs';

// Login with role awareness
<button
  {...authAutomationAttrs('login', isLoading ? 'loading' : 'ready', userRole)}
  disabled={isLoading}
  onClick={handleLogin}
>
  {isLoading ? 'Logging in...' : 'Login'}
</button>

// Generates:
// id="auth-login"
// data-testid="auth-login"
// data-entity="auth"
// data-action="login"
// data-context="auth"
// data-state="ready"
// data-auth-role="ROOT_ADMIN"
```

### Subscription Management Pattern (SaaS)
```tsx
import { subscriptionAutomationAttrs } from '@/app/utils/automation-attrs';

// Subscription plan selection
<button
  {...subscriptionAutomationAttrs('select', plan.id, 'available')}
  onClick={() => selectPlan(plan.id)}
>
  Select {plan.name}
</button>

// Generates:
// id="subscription-select-pro"
// data-testid="subscription-select"
// data-entity="subscription"
// data-action="select"
// data-context="admin"
// data-subscription-plan="pro"
// data-state="available"
```

### Multi-Tenant Pattern
```tsx
import { tenantAutomationAttrs } from '@/app/utils/automation-attrs';

// Tenant-specific actions
<button
  {...tenantAutomationAttrs('assign', tenant.id, 'wedding_planner')}
  onClick={() => assignWedding(tenant.id)}
>
  Assign Wedding
</button>

// Generates:
// id="tenant-assign-789"
// data-testid="tenant-assign"
// data-entity="tenant"
// data-action="assign"
// data-context="admin"
// data-tenant-id="789"
// data-tenant-role="wedding_planner"
```

## Form Patterns

### Dynamic Form Fields
```tsx
import { formAutomationAttrs } from '@/app/utils/automation-attrs';

// Form field with validation state
<input
  {...formAutomationAttrs(formId, field.id, 'input', {
    valid: !errors[field.id],
    required: field.required,
    touched: touched[field.id]
  })}
  value={values[field.id]}
  onChange={(e) => handleChange(field.id, e.target.value)}
/>

// Generates:
// id="form-input-contact"
// data-testid="form-input"
// data-entity="form"
// data-action="input"
// data-form-id="contact"
// data-field-id="email"
// data-field-valid="true"
// data-field-required="true"
// data-field-touched="false"
```

### Form Submission
```tsx
// Submit button with form state
<button
  {...formAutomationAttrs(formId, undefined, 'submit')}
  data-form-valid={isFormValid}
  disabled={!isFormValid || isSubmitting}
>
  {isSubmitting ? 'Submitting...' : 'Submit'}
</button>
```

## Navigation Patterns

### Admin Navigation
```tsx
import { navigationAttrs } from '@/app/utils/automation-attrs';

// Admin sidebar navigation
<button
  {...navigationAttrs('/admin/guests', 'sidebar')}
  onClick={() => router.push('/admin/guests')}
>
  Manage Guests
</button>

// Generates:
// id="navigation-navigate"
// data-testid="navigation-navigate"
// data-entity="navigation"
// data-action="navigate"
// data-context="nav"
// data-destination="/admin/guests"
```

### Breadcrumb Navigation
```tsx
// Breadcrumb with context
<button
  {...navigationAttrs('/admin/weddings', 'breadcrumb')}
  onClick={() => router.push('/admin/weddings')}
>
  Weddings
</button>
```

## State-Aware Patterns

### Loading States
```tsx
// Button with loading state
<button
  {...createAutomationAttrs({
    entity: 'guest',
    action: 'create',
    state: isCreating ? 'loading' : 'ready'
  })}
  disabled={isCreating}
>
  {isCreating ? 'Creating...' : 'Create Guest'}
</button>
```

### Validation States
```tsx
// Input with validation state
<input
  {...createAutomationAttrs({
    entity: 'form',
    action: 'input',
    custom: {
      'field-valid': isValid.toString(),
      'field-error': hasError.toString()
    }
  })}
/>
```

## List and Table Patterns

### Data Tables
```tsx
// Table row with entity identification
<tr {...guestAutomationAttrs(guest, 'row')}>
  <td>{guest.name}</td>
  <td>
    <button {...guestAutomationAttrs(guest, 'edit')}>
      Edit
    </button>
    <button {...guestAutomationAttrs(guest, 'delete')}>
      Delete
    </button>
  </td>
</tr>
```

### Pagination
```tsx
// Pagination controls
<button
  {...createAutomationAttrs({
    entity: 'pagination',
    action: 'next',
    custom: {
      'current-page': currentPage.toString(),
      'total-pages': totalPages.toString()
    }
  })}
  disabled={currentPage >= totalPages}
>
  Next Page
</button>
```

## Modal and Dialog Patterns

### Modal Actions
```tsx
// Modal with context-aware actions
<div {...createAutomationAttrs({
  entity: 'modal',
  action: 'container',
  context: 'guest-edit'
})}>
  <button {...createAutomationAttrs({
    entity: 'modal',
    action: 'close',
    context: 'guest-edit'
  })}>
    ×
  </button>

  <button {...createAutomationAttrs({
    entity: 'modal',
    action: 'save',
    context: 'guest-edit',
    state: isValid ? 'ready' : 'disabled'
  })}>
    Save Changes
  </button>
</div>
```

## Search and Filter Patterns

### Search Controls
```tsx
// Search input with entity context
<input
  {...createAutomationAttrs({
    entity: 'search',
    action: 'input',
    context: 'guest-list',
    custom: {
      'search-type': 'guest-name'
    }
  })}
  placeholder="Search guests..."
  onChange={(e) => setSearchTerm(e.target.value)}
/>
```

### Filter Controls
```tsx
// Filter dropdown
<select
  {...createAutomationAttrs({
    entity: 'filter',
    action: 'select',
    context: 'guest-list',
    custom: {
      'filter-type': 'role'
    }
  })}
  value={selectedRole}
  onChange={(e) => setSelectedRole(e.target.value)}
>
  <option value="">All Roles</option>
  <option value="guest">Guest</option>
  <option value="vip">VIP</option>
</select>
```

## Testing Usage Examples

### Playwright Examples
```typescript
// Target specific guest actions
await page.click('[data-guest-id="123"][data-action="delete"]');

// Wait for loading to complete
await page.waitForSelector('[data-state="ready"]');

// Find all ready submit buttons
const submitButtons = page.locator('[data-action="submit"][data-state="ready"]');

// Target admin context actions
await page.click('[data-context="admin"][data-action="create"]');

// Multi-tenant role-based targeting
await page.click('[data-tenant-role="wedding_planner"][data-action="assign"]');
```

### Cypress Examples
```typescript
// Guest management workflow
cy.get('[data-entity="guest"][data-action="create"]').click();
cy.get('[data-field-id="name"]').type('John Doe');
cy.get('[data-field-valid="true"]').should('exist');
cy.get('[data-action="submit"][data-state="ready"]').click();

// Subscription workflow
cy.get('[data-subscription-plan="pro"][data-action="select"]').click();
cy.get('[data-state="loading"]').should('exist');
cy.get('[data-state="ready"]').should('exist');
```

## Best Practices

### Naming Conventions
- Use lowercase with hyphens for multi-word values
- Be descriptive but concise
- Follow entity-action-context pattern
- Include state information when relevant

### State Management
- Always include loading states for async operations
- Use validation states for forms
- Include error states for better debugging
- Context-aware attributes for better targeting

### Multi-Tenant Considerations
- Include role information for permission-based testing
- Use tenant-scoped identifiers
- Context-aware targeting for different user types
- Permission state tracking

---

*This pattern library is continuously updated as new patterns emerge during implementation.*
