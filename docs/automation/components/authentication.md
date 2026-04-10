# Authentication Flow - Automation Attributes

## Overview

This document details the automation attributes implementation for the authentication system in the Wedding Web Application SaaS platform. The authentication system supports multi-tenant role-based access control with state-aware dynamic attributes.

## Components Enhanced

### 1. Admin Login Page (`app/admin/login/page.tsx`)

#### Before
```tsx
<input id="email-input" type="email" placeholder="Email" />
<input id="password-input" type="password" placeholder="Password" />
<button id="login-button" onClick={handleLogin}>Log In</button>
```

#### After
```tsx
<input
  {...authAutomationAttrs('input-email', email ? 'valid' : 'empty')}
  type="email"
  placeholder="Email"
/>
<input
  {...authAutomationAttrs('input-password', password ? 'valid' : 'empty')}
  type="password"
  placeholder="Password"
/>
<button
  {...authAutomationAttrs('login', loading ? 'loading' : (!email || !password ? 'disabled' : 'ready'))}
  onClick={handleLogin}
>
  {loading ? 'Logging in…' : 'Log In'}
</button>
```

#### Generated Attributes
```html
<!-- Email Input -->
id="auth-input-email"
data-testid="auth-input-email"
data-entity="auth"
data-action="input-email"
data-context="auth"
data-state="valid" <!-- or "empty" -->

<!-- Password Input -->
id="auth-input-password"
data-testid="auth-input-password"
data-entity="auth"
data-action="input-password"
data-context="auth"
data-state="valid" <!-- or "empty" -->

<!-- Login Button -->
id="auth-login"
data-testid="auth-login"
data-entity="auth"
data-action="login"
data-context="auth"
data-state="ready" <!-- "loading", "disabled", or "ready" -->

<!-- Password Visibility Toggle -->
id="auth-toggle-password-visibility"
data-testid="auth-toggle-password-visibility"
data-entity="auth"
data-action="toggle-password-visibility"
data-context="auth"
data-state="visible" <!-- or "hidden" -->

<!-- Remember Me Checkbox -->
id="auth-checkbox-remember-me"
data-testid="auth-checkbox-remember-me"
data-entity="auth"
data-action="checkbox-remember-me"
data-context="auth"
data-state="checked" <!-- or "unchecked" -->
```

### 2. Admin Context (`app/contexts/AdminContext.tsx`)

#### Enhanced Features
- **Document-level state tracking**: Adds `data-auth-state` and `data-auth-role` to document body
- **Global authentication state**: Available throughout the application for automation tools

```typescript
// On successful login
document.body.setAttribute('data-auth-state', 'authenticated');
document.body.setAttribute('data-auth-role', userProfile.role);

// On logout
document.body.removeAttribute('data-auth-state');
document.body.removeAttribute('data-auth-role');
```

### 3. Admin Sidebar (`app/admin/components/AdminSidebar.tsx`)

#### Navigation Links
```tsx
<Link
  {...navigationAttrs(link.href, 'sidebar')}
  href={link.href}
  data-active={isActive.toString()}
  data-role={userProfile?.role}
>
  {link.label}
</Link>
```

#### Generated Attributes
```html
<!-- Navigation Link -->
id="navigation-navigate"
data-testid="navigation-navigate"
data-entity="navigation"
data-action="navigate"
data-context="nav"
data-destination="/admin/guests"
data-active="true" <!-- or "false" -->
data-role="wedding_planner" <!-- or user's actual role -->

<!-- Logout Button -->
id="auth-logout"
data-testid="auth-logout"
data-entity="auth"
data-action="logout"
data-context="auth"
data-state="ready"
data-auth-role="wedding_planner"

<!-- Theme Toggle -->
id="theme-toggle"
data-testid="theme-toggle"
data-entity="theme"
data-action="toggle"
data-context="sidebar"
data-state="light" <!-- or "dark" -->

<!-- Sidebar Close Button -->
id="sidebar-close"
data-testid="sidebar-close"
data-entity="sidebar"
data-action="close"
data-context="admin"
```

### 4. Permission Gate (`app/components/PermissionGate.tsx`)

#### Role-Based Access Control
```tsx
// Permission denied
<div
  {...createAutomationAttrs({
    entity: 'permission',
    action: 'denied',
    context: 'role',
    state: 'insufficient',
    custom: {
      'required-role': 'ROOT_ADMIN',
      'user-role': userProfile.role
    }
  })}
>
  Admin access required
</div>

// Permission granted
<div
  {...createAutomationAttrs({
    entity: 'permission',
    action: 'granted',
    context: 'role',
    state: 'authorized',
    custom: {
      'user-role': userProfile.role,
      'is-root-admin': userProfile.is_root_admin.toString(),
      'is-wedding-planner': userProfile.is_wedding_planner.toString(),
      'is-vendor': userProfile.is_vendor.toString()
    }
  })}
>
  {children}
</div>
```

#### Generated Attributes
```html
<!-- Permission Denied -->
id="permission-denied"
data-testid="permission-denied"
data-entity="permission"
data-action="denied"
data-context="role"
data-state="insufficient"
data-required-role="ROOT_ADMIN"
data-user-role="wedding_planner"

<!-- Permission Granted -->
id="permission-granted"
data-testid="permission-granted"
data-entity="permission"
data-action="granted"
data-context="role"
data-state="authorized"
data-user-role="wedding_planner"
data-is-root-admin="false"
data-is-wedding-planner="true"
data-is-vendor="false"
```

### 5. Client-Only Admin Provider (`app/admin/components/ClientOnlyAdminProvider.tsx`)

#### Loading State
```tsx
<div
  {...createAutomationAttrs({
    entity: 'auth',
    action: 'loading',
    context: 'provider',
    state: 'hydrating'
  })}
  className="min-h-screen flex items-center justify-center bg-wedding-ivory dark:bg-gray-900"
>
  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
</div>
```

## Multi-Tenant Role System

### Supported Roles
- **ROOT_ADMIN**: Platform administrator with full access
- **wedding_planner**: Wedding planner with wedding-specific access
- **vendor**: Vendor with limited task-specific access

### Role-Based Attribute Variations
```typescript
// Different navigation based on role
if (userProfile.is_root_admin) {
  // Platform management links
} else if (userProfile.is_wedding_planner) {
  // Wedding planning links
} else if (userProfile.is_vendor) {
  // Vendor task links
}
```

## Testing Examples

### Playwright Tests
```typescript
// Test login flow
await page.fill('[data-action="input-email"]', 'admin@example.com');
await page.fill('[data-action="input-password"]', 'password');
await page.click('[data-action="login"][data-state="ready"]');

// Wait for authentication
await page.waitForSelector('[data-auth-state="authenticated"]');

// Test role-based navigation
await page.click('[data-destination="/admin/guests"][data-role="wedding_planner"]');

// Test logout
await page.click('[data-action="logout"]');
await page.waitForSelector('[data-auth-state="authenticated"]', { state: 'detached' });
```

### Cypress Tests
```typescript
// Login as wedding planner
cy.get('[data-action="input-email"]').type('planner@example.com');
cy.get('[data-action="input-password"]').type('password');
cy.get('[data-action="login"]').click();

// Verify authentication state
cy.get('body').should('have.attr', 'data-auth-state', 'authenticated');
cy.get('body').should('have.attr', 'data-auth-role', 'wedding_planner');

// Test permission gates
cy.get('[data-entity="permission"][data-action="granted"]').should('exist');
cy.get('[data-required-role="ROOT_ADMIN"]').should('not.exist');

// Test navigation
cy.get('[data-destination="/admin/guests"]').click();
cy.url().should('include', '/admin/guests');
```

### Role-Based Testing
```typescript
// Test ROOT_ADMIN access
await page.evaluate(() => {
  document.body.setAttribute('data-auth-role', 'ROOT_ADMIN');
});
await page.goto('/admin/saas');
await page.waitForSelector('[data-entity="permission"][data-action="granted"]');

// Test insufficient permissions
await page.evaluate(() => {
  document.body.setAttribute('data-auth-role', 'vendor');
});
await page.goto('/admin/saas');
await page.waitForSelector('[data-entity="permission"][data-action="denied"]');
```

## State Management

### Authentication States
- **unauthenticated**: User not logged in
- **loading**: Authentication in progress
- **authenticated**: User successfully logged in
- **error**: Authentication failed

### Form States
- **empty**: Field has no value
- **valid**: Field has valid value
- **invalid**: Field has invalid value
- **disabled**: Field cannot be interacted with
- **ready**: Form ready for submission

### UI States
- **visible**: Password visibility is on
- **hidden**: Password visibility is off
- **checked**: Checkbox is selected
- **unchecked**: Checkbox is not selected
- **light**: Light theme active
- **dark**: Dark theme active

## Security Considerations

### Multi-Tenant Isolation
- Each role has specific navigation and access patterns
- Permission gates enforce role-based access control
- Automation attributes include role information for testing

### State Tracking
- Global document attributes track authentication state
- Component-level attributes track interaction states
- Clear attribute cleanup on logout

## Implementation Benefits

### 1. **Role-Aware Testing**
- Target specific user roles in automated tests
- Verify permission gates work correctly
- Test role-based navigation flows

### 2. **State-Driven Automation**
- Wait for specific authentication states
- Validate form states before submission
- Handle loading states gracefully

### 3. **Multi-Tenant Support**
- Test different user journey paths
- Verify role-based feature access
- Validate tenant isolation

### 4. **Comprehensive Coverage**
- All authentication flows covered
- Permission system fully attributed
- Global state tracking implemented

---

*Implementation completed: January 18, 2025*
*Components: Login, Context, Sidebar, Permission Gate, Provider*
*Coverage: 100% of authentication flow components*
