// Automation Attributes Utility
// Provides consistent, dynamic automation targeting

export interface AutomationAttrs {
  id?: string;
  'data-testid'?: string;
  'data-entity'?: string;
  'data-action'?: string;
  'data-state'?: string;
  'data-context'?: string;
  [key: string]: string | undefined;
}

/**
 * Generate automation attributes for consistent testing
 */
export function createAutomationAttrs(config: {
  // Base identifier
  id?: string;
  testid?: string;

  // Semantic context
  entity?: string;      // 'guest', 'form', 'wedding', etc.
  action?: string;      // 'delete', 'edit', 'submit', etc.
  context?: string;     // 'admin', 'public', 'modal', etc.

  // Dynamic data
  entityId?: string | number;
  state?: string;       // 'loading', 'disabled', 'active', etc.

  // Custom attributes
  custom?: Record<string, string | number | boolean>;
}): AutomationAttrs {
  const attrs: AutomationAttrs = {};

  // Generate ID if not provided
  if (config.id) {
    attrs.id = config.id;
  } else if (config.entity && config.action) {
    attrs.id = `${config.entity}-${config.action}${config.entityId ? `-${config.entityId}` : ''}`;
  }

  // Test ID for automation tools
  if (config.testid) {
    attrs['data-testid'] = config.testid;
  } else if (config.entity && config.action) {
    attrs['data-testid'] = `${config.entity}-${config.action}`;
  }

  // Semantic attributes
  if (config.entity) attrs['data-entity'] = config.entity;
  if (config.action) attrs['data-action'] = config.action;
  if (config.context) attrs['data-context'] = config.context;
  if (config.state) attrs['data-state'] = config.state;

  // Entity-specific attributes
  if (config.entityId) attrs[`data-${config.entity}-id`] = String(config.entityId);

  // Custom attributes
  if (config.custom) {
    Object.entries(config.custom).forEach(([key, value]) => {
      attrs[`data-${key}`] = String(value);
    });
  }

  return attrs;
}

/**
 * Guest-specific automation attributes
 */
export function guestAutomationAttrs(guest: { id: string; name: string }, action: string, context = 'admin') {
  return createAutomationAttrs({
    entity: 'guest',
    action,
    context,
    entityId: guest.id,
    custom: {
      'guest-name': guest.name.replace(/\s+/g, '-').toLowerCase(),
    }
  });
}

/**
 * Form-specific automation attributes
 */
export function formAutomationAttrs(
  formId: string,
  fieldId?: string,
  action = 'input',
  state?: { valid?: boolean; required?: boolean; touched?: boolean }
) {
  return createAutomationAttrs({
    entity: 'form',
    action,
    entityId: formId,
    custom: {
      'form-id': formId,
      'field-id': fieldId || '',
      'field-valid': state?.valid?.toString() || '',
      'field-required': state?.required?.toString() || '',
      'field-touched': state?.touched?.toString() || '',
    }
  });
}

/**
 * Admin action automation attributes
 */
export function adminActionAttrs(
  action: string,
  entity: string,
  entityId?: string | number,
  state?: string
) {
  return createAutomationAttrs({
    entity,
    action,
    context: 'admin',
    entityId,
    state
  });
}

/**
 * Navigation automation attributes
 */
export function navigationAttrs(destination: string, context = 'nav') {
  return createAutomationAttrs({
    entity: 'navigation',
    action: 'navigate',
    context,
    custom: {
      destination
    }
  });
}

/**
 * Wedding-specific automation attributes
 */
export function weddingAutomationAttrs(
  wedding: { id: string; couple_names: string },
  action: string,
  context = 'admin'
) {
  return createAutomationAttrs({
    entity: 'wedding',
    action,
    context,
    entityId: wedding.id,
    custom: {
      'wedding-names': wedding.couple_names.replace(/\s+/g, '-').toLowerCase(),
    }
  });
}

/**
 * Authentication automation attributes
 */
export function authAutomationAttrs(
  action: string,
  state?: string,
  role?: string
) {
  return createAutomationAttrs({
    entity: 'auth',
    action,
    context: 'auth',
    state,
    custom: {
      'auth-role': role || '',
    }
  });
}

/**
 * Subscription automation attributes (SaaS platform)
 */
export function subscriptionAutomationAttrs(
  action: string,
  planId?: string,
  state?: string
) {
  return createAutomationAttrs({
    entity: 'subscription',
    action,
    context: 'admin',
    entityId: planId,
    state,
    custom: {
      'subscription-plan': planId || '',
    }
  });
}

/**
 * Multi-tenant automation attributes
 */
export function tenantAutomationAttrs(
  action: string,
  tenantId: string,
  role: 'ROOT_ADMIN' | 'wedding_planner' | 'vendor'
) {
  return createAutomationAttrs({
    entity: 'tenant',
    action,
    context: 'admin',
    entityId: tenantId,
    custom: {
      'tenant-role': role,
    }
  });
}

// Automation CSS selectors helper
export const automationSelectors = {
  // By test ID
  testId: (id: string) => `[data-testid="${id}"]`,

  // By entity and action
  entityAction: (entity: string, action: string) =>
    `[data-entity="${entity}"][data-action="${action}"]`,

  // By entity ID
  entityById: (entity: string, id: string) =>
    `[data-entity="${entity}"][data-${entity}-id="${id}"]`,

  // By state
  withState: (state: string) => `[data-state="${state}"]`,

  // By context
  inContext: (context: string) => `[data-context="${context}"]`,

  // By role (multi-tenant)
  withRole: (role: string) => `[data-tenant-role="${role}"]`,

  // Complex selectors for SaaS platform
  guestAction: (guestId: string, action: string) =>
    `[data-entity="guest"][data-action="${action}"][data-guest-id="${guestId}"]`,

  weddingAction: (weddingId: string, action: string) =>
    `[data-entity="wedding"][data-action="${action}"][data-wedding-id="${weddingId}"]`,

  formField: (formId: string, fieldId?: string) =>
    fieldId
      ? `[data-entity="form"][data-form-id="${formId}"][data-field-id="${fieldId}"]`
      : `[data-entity="form"][data-form-id="${formId}"]`,

  subscriptionAction: (action: string, planId?: string) =>
    planId
      ? `[data-entity="subscription"][data-action="${action}"][data-subscription-plan="${planId}"]`
      : `[data-entity="subscription"][data-action="${action}"]`,

  tenantAction: (action: string, role: string) =>
    `[data-entity="tenant"][data-action="${action}"][data-tenant-role="${role}"]`,

  // State-aware selectors
  readyElement: (entity: string, action: string) =>
    `[data-entity="${entity}"][data-action="${action}"][data-state="ready"]`,

  loadingElement: (entity: string, action: string) =>
    `[data-entity="${entity}"][data-action="${action}"][data-state="loading"]`,

  validField: (entity: string) =>
    `[data-entity="${entity}"][data-field-valid="true"]`,

  // Admin context selectors
  adminAction: (entity: string, action: string) =>
    `[data-entity="${entity}"][data-action="${action}"][data-context="admin"]`,
};