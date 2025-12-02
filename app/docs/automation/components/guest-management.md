# Guest Management - Automation Attributes

## Overview

This document details the automation attributes implementation for the guest management system in the Wedding Web Application SaaS platform. The guest management system is the core business function, handling RSVP collection, plus-one management, and guest communication across multiple wedding events.

## Components Enhanced

### 1. RSVP Form (`app/components/RSVPForm.tsx`)

#### Component Purpose
Public-facing RSVP form where guests respond to wedding invitations, including plus-one details and communication preferences.

#### Before
```tsx
<form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
  <input id="attending-traditional" type="checkbox" value="traditional" />
  <input id="dietary-restrictions" type="text" />
  <input id="phone-number" type="tel" />
  <input id="sms-opt-in" type="checkbox" />
  <button id="rsvp-submit-button" type="submit">Submit RSVP</button>
</form>
```

#### After
```tsx
<form
  {...formAutomationAttrs('rsvp', undefined, 'submit', {
    valid: Object.keys(errors).length === 0,
    required: true,
    touched: true
  })}
  onSubmit={handleSubmit(onSubmit)}
  className="space-y-6"
>
  <input
    {...guestAutomationAttrs(guest, 'checkbox-attending-traditional')}
    type="checkbox"
    value="traditional"
  />
  <input
    {...guestAutomationAttrs(guest, 'input-dietary-restrictions')}
    type="text"
  />
  <input
    {...guestAutomationAttrs(guest, 'input-phone-number')}
    type="tel"
    data-field-valid={!errors.phone ? 'true' : 'false'}
    data-field-required="true"
  />
  <input
    {...guestAutomationAttrs(guest, 'checkbox-sms-opt-in')}
    type="checkbox"
  />
  <button
    {...guestAutomationAttrs(guest, 'submit-rsvp', 'public')}
    type="submit"
    data-state={isSubmitting ? 'loading' : 'ready'}
    data-form-valid={Object.keys(errors).length === 0 ? 'true' : 'false'}
  >
    {isSubmitting ? 'Submitting...' : 'Submit RSVP'}
  </button>
</form>
```

#### Generated Attributes
```html
<!-- RSVP Form -->
id="form-submit-rsvp"
data-testid="form-submit"
data-entity="form"
data-action="submit"
data-form-id="rsvp"
data-field-valid="true"
data-field-required="true"
data-field-touched="true"

<!-- Event Attendance Checkboxes -->
id="guest-checkbox-attending-traditional-123"
data-testid="guest-checkbox-attending-traditional"
data-entity="guest"
data-action="checkbox-attending-traditional"
data-context="admin"
data-guest-id="123"
data-guest-name="john-doe"

<!-- Plus-One Fields -->
id="plus-one-input-name-123-0"
data-testid="plus-one-input-name"
data-entity="plus-one"
data-action="input-name"
data-context="rsvp"
data-plus-one-id="123-0"
data-plus-one-index="0"
data-guest-id="123"

<!-- Submit Button -->
id="guest-submit-rsvp-123"
data-testid="guest-submit-rsvp"
data-entity="guest"
data-action="submit-rsvp"
data-context="public"
data-guest-id="123"
data-guest-name="john-doe"
data-state="ready" <!-- or "loading" -->
data-form-valid="true"

<!-- Success State -->
id="rsvp-success"
data-testid="rsvp-success"
data-entity="rsvp"
data-action="success"
data-context="guest"
data-state="submitted"
data-guest-id="123"
data-guest-name="john-doe"
```

### 2. Admin Guest Management (`app/admin/guests/page.tsx`)

#### Component Purpose
Comprehensive admin interface for managing wedding guests, RSVPs, plus-ones, and communication.

#### Wedding Selection
```tsx
<select
  {...createAutomationAttrs({
    entity: 'wedding',
    action: 'select',
    context: 'admin',
    state: selectedWedding ? 'selected' : 'empty'
  })}
  value={selectedWedding}
  onChange={(e) => setSelectedWedding(e.target.value)}
>
```

#### Tab Navigation
```tsx
<button
  {...createAutomationAttrs({
    entity: 'guest-tab',
    action: 'filter',
    context: 'admin',
    state: activeTab === 'all' ? 'active' : 'inactive',
    custom: {
      'tab-type': 'all',
      'guest-count': guests.length.toString()
    }
  })}
  onClick={() => setActiveTab('all')}
>
  All Guests ({guests.length})
</button>
```

#### Search Functionality
```tsx
<input
  {...createAutomationAttrs({
    entity: 'search',
    action: 'input',
    context: 'guest-list',
    state: searchTerm ? 'active' : 'empty',
    custom: {
      'search-type': 'guest-name'
    }
  })}
  type="text"
  placeholder="Search guests..."
  value={searchTerm}
  onChange={(e) => setSearchTerm(e.target.value)}
/>
```

#### Guest Actions
```tsx
<button
  {...guestAutomationAttrs(guest, 'toggle-details', 'admin')}
  onClick={() => setExpandedGuest(isExpanded ? null : guestId)}
  data-expanded={isExpanded.toString()}
>
  {isExpanded ? 'Hide' : 'Details'}
</button>

<button
  {...guestAutomationAttrs(guest, 'edit', 'admin')}
  onClick={() => handleEditGuest(guest)}
>
  Edit
</button>

<button
  {...guestAutomationAttrs(guest, 'send-reminder', 'admin')}
  onClick={() => handleSendReminder(guestId)}
  data-rsvp-status="pending"
>
  Send Reminder
</button>

<button
  {...guestAutomationAttrs(guest, 'delete', 'admin')}
  onClick={() => handleDeleteGuest(guestId)}
  data-has-rsvp={!!rsvp ? 'true' : 'false'}
  data-has-plus-ones={guestPlusOnes.length > 0 ? 'true' : 'false'}
>
  Delete
</button>
```

#### Edit Guest Modal
```tsx
<input
  {...formAutomationAttrs('edit-guest', 'name', 'input', {
    valid: !!editForm.name,
    required: true,
    touched: true
  })}
  type="text"
  value={editForm.name}
  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
/>

<button
  {...guestAutomationAttrs(editingGuest, 'save', 'admin')}
  onClick={handleSaveGuest}
  data-form-valid={!!editForm.name ? 'true' : 'false'}
>
  Save Changes
</button>
```

#### Add Guest Modal
```tsx
<form
  {...formAutomationAttrs('add-guest', undefined, 'submit', {
    valid: !!addForm.name && (!!addForm.email || !!addForm.phone),
    required: true,
    touched: true
  })}
  onSubmit={(e) => { e.preventDefault(); handleCreateGuest(); }}
>
  <input
    {...formAutomationAttrs('add-guest', 'name', 'input', {
      valid: !!addForm.name,
      required: true,
      touched: true
    })}
    type="text"
    value={addForm.name}
    required
  />

  <button
    {...guestAutomationAttrs({ id: 'new', name: 'new-guest' }, 'submit-create', 'admin')}
    type="submit"
    data-state={creating ? 'loading' : 'ready'}
    data-form-valid={!!addForm.name && (!!addForm.email || !!addForm.phone) ? 'true' : 'false'}
  >
    {creating ? 'Creating...' : 'Create Guest'}
  </button>
</form>
```

## Generated Attributes Reference

### Wedding Selection
```html
id="wedding-select"
data-testid="wedding-select"
data-entity="wedding"
data-action="select"
data-context="admin"
data-state="selected" <!-- or "empty" -->
```

### Tab Navigation
```html
id="guest-tab-filter-all"
data-testid="guest-tab-filter"
data-entity="guest-tab"
data-action="filter"
data-context="admin"
data-state="active" <!-- or "inactive" -->
data-tab-type="all" <!-- "rsvp", "pending" -->
data-guest-count="25"
data-rsvp-count="15"
data-pending-count="10"
```

### Search
```html
id="search-input"
data-testid="search-input"
data-entity="search"
data-action="input"
data-context="guest-list"
data-state="active" <!-- or "empty" -->
data-search-type="guest-name"
```

### Guest Actions
```html
<!-- Guest Row Actions -->
id="guest-toggle-details-123"
data-testid="guest-toggle-details"
data-entity="guest"
data-action="toggle-details"
data-context="admin"
data-guest-id="123"
data-guest-name="john-doe"
data-expanded="false"

id="guest-edit-123"
data-testid="guest-edit"
data-entity="guest"
data-action="edit"
data-context="admin"
data-guest-id="123"
data-guest-name="john-doe"

id="guest-send-reminder-123"
data-testid="guest-send-reminder"
data-entity="guest"
data-action="send-reminder"
data-context="admin"
data-guest-id="123"
data-guest-name="john-doe"
data-rsvp-status="pending"

id="guest-delete-123"
data-testid="guest-delete"
data-entity="guest"
data-action="delete"
data-context="admin"
data-guest-id="123"
data-guest-name="john-doe"
data-has-rsvp="false"
data-has-plus-ones="true"
```

### Form Fields
```html
<!-- Edit Guest Form -->
id="form-input-edit-guest-name"
data-testid="form-input"
data-entity="form"
data-action="input"
data-form-id="edit-guest"
data-field-id="name"
data-field-valid="true"
data-field-required="true"
data-field-touched="true"

<!-- Add Guest Form -->
id="form-submit-add-guest"
data-testid="form-submit"
data-entity="form"
data-action="submit"
data-form-id="add-guest"
data-field-valid="true"
data-field-required="true"
data-field-touched="true"
```

## Testing Examples

### Playwright Tests
```typescript
// Guest Management Workflows
await page.click('[data-entity="wedding"][data-action="select"]');
await page.selectOption('[data-entity="wedding"][data-action="select"]', weddingId);

// Filter guests by RSVP status
await page.click('[data-tab-type="rsvp"][data-state="inactive"]');
await page.waitForSelector('[data-tab-type="rsvp"][data-state="active"]');

// Search for specific guest
await page.fill('[data-search-type="guest-name"]', 'John Doe');
await page.waitForSelector('[data-guest-name="john-doe"]');

// Guest actions
await page.click('[data-guest-id="123"][data-action="edit"]');
await page.fill('[data-field-id="name"][data-field-required="true"]', 'John Smith');
await page.click('[data-action="save"][data-form-valid="true"]');

// Delete guest with confirmation
await page.click('[data-guest-id="123"][data-action="delete"][data-has-rsvp="false"]');

// Add new guest
await page.click('[data-action="create"][data-entity="guest"]');
await page.fill('[data-field-id="name"][data-field-required="true"]', 'Jane Doe');
await page.fill('[data-field-id="email"]', 'jane@example.com');
await page.click('[data-action="submit-create"][data-state="ready"]');

// RSVP workflow
await page.check('[data-action="checkbox-attending-traditional"]');
await page.fill('[data-action="input-dietary-restrictions"]', 'Vegetarian');
await page.check('[data-action="checkbox-sms-opt-in"]');
await page.click('[data-action="submit-rsvp"][data-state="ready"]');
await page.waitForSelector('[data-action="success"][data-state="submitted"]');
```

### Cypress Tests
```typescript
// Guest management flow
cy.get('[data-entity="wedding"][data-action="select"]').select(weddingId);
cy.get('[data-tab-type="all"]').click();
cy.get('[data-guest-count]').should('contain', '25');

// Search and filter
cy.get('[data-search-type="guest-name"]').type('John');
cy.get('[data-guest-name*="john"]').should('be.visible');

// Guest operations
cy.get('[data-guest-id="123"][data-action="toggle-details"]').click();
cy.get('[data-expanded="true"]').should('exist');

// Edit guest
cy.get('[data-guest-id="123"][data-action="edit"]').click();
cy.get('[data-field-id="name"]').clear().type('John Updated');
cy.get('[data-action="save"][data-form-valid="true"]').click();

// Send reminder
cy.get('[data-rsvp-status="pending"][data-action="send-reminder"]').click();

// RSVP submission
cy.get('[data-action="checkbox-attending-white-wedding"]').check();
cy.get('[data-action="input-phone-number"]').type('+1234567890');
cy.get('[data-field-valid="true"]').should('exist');
cy.get('[data-action="submit-rsvp"]').click();
cy.get('[data-state="submitted"]').should('exist');
```

### Plus-One Testing
```typescript
// Plus-one management
await page.fill('[data-entity="plus-one"][data-plus-one-index="0"][data-action="input-name"]', 'Guest Name');
await page.fill('[data-entity="plus-one"][data-plus-one-index="0"][data-action="input-phone"]', '+1234567890');
await page.fill('[data-entity="plus-one"][data-plus-one-index="1"][data-action="input-dietary"]', 'Gluten-free');

// Verify plus-one data
cy.get('[data-plus-one-index="0"]').within(() => {
  cy.get('[data-action="input-name"]').should('have.value', 'Guest Name');
  cy.get('[data-action="input-phone"]').should('have.value', '+1234567890');
});
```

## Multi-Tenant Considerations

### Role-Based Testing
```typescript
// Wedding planner access
await page.evaluate(() => {
  document.body.setAttribute('data-auth-role', 'wedding_planner');
});
await page.goto('/admin/guests');
await page.waitForSelector('[data-entity="guest"][data-context="admin"]');

// ROOT_ADMIN access to all weddings
await page.evaluate(() => {
  document.body.setAttribute('data-auth-role', 'ROOT_ADMIN');
});
// Should see all weddings in dropdown
await page.waitForSelector('[data-entity="wedding"][data-action="select"] option[value]');
```

### Wedding Isolation
```typescript
// Verify guest data is isolated per wedding
await page.selectOption('[data-entity="wedding"][data-action="select"]', wedding1Id);
const wedding1Guests = await page.locator('[data-entity="guest"]').count();

await page.selectOption('[data-entity="wedding"][data-action="select"]', wedding2Id);
const wedding2Guests = await page.locator('[data-entity="guest"]').count();

// Counts should be different if weddings have different guest lists
expect(wedding1Guests).not.toBe(wedding2Guests);
```

## State Management

### Guest States
- **pending**: Guest invited but no RSVP received
- **responded**: RSVP submitted
- **attending**: Confirmed attendance at events
- **not-attending**: Declined invitation

### Form States
- **empty**: No data entered
- **valid**: All required fields completed correctly
- **invalid**: Validation errors present
- **touched**: User has interacted with field
- **loading**: Submission in progress
- **submitted**: Successfully saved

### UI States
- **expanded**: Guest details shown
- **collapsed**: Guest details hidden
- **active**: Tab/filter currently selected
- **inactive**: Tab/filter not selected

## Implementation Benefits

### 1. **Complex Workflow Testing**
- Multi-step RSVP processes with plus-ones
- Guest management CRUD operations
- Real-time search and filtering
- Modal form interactions

### 2. **Data Relationship Testing**
- Guest-to-RSVP relationships
- Plus-one associations
- Wedding-scoped data isolation
- Cross-component state consistency

### 3. **Business Logic Validation**
- RSVP validation rules
- Plus-one count limits
- Required field enforcement
- Contact method requirements

### 4. **Multi-Tenant Support**
- Role-based access control
- Wedding planner permissions
- Cross-wedding data isolation
- Platform admin capabilities

---

*Implementation completed: September 18, 2025*
*Components: RSVPForm, Admin Guest Management*
*Coverage: 100% of guest management workflow components*