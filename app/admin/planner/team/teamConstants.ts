// Shared team management constants
export const ROLES = [
  { value: 'admin', label: 'Admin', desc: 'Full access to everything', color: 'text-wedding-rose' },
  { value: 'editor', label: 'Editor', desc: 'Create & edit content', color: 'text-wedding-sage' },
  { value: 'viewer', label: 'Viewer', desc: 'Read-only access', color: 'text-slate-400' },
];

export const ALL_PERMISSIONS = [
  { key: 'manage_guests', label: 'Manage Guests' },
  { key: 'manage_budget', label: 'Manage Budget' },
  { key: 'manage_gallery', label: 'Manage Gallery' },
  { key: 'manage_seating', label: 'Manage Seating' },
  { key: 'manage_vendors', label: 'Manage Vendors' },
  { key: 'send_rsvp', label: 'Send RSVP' },
  { key: 'send_reminders', label: 'Send Reminders' },
  { key: 'manage_forms', label: 'Manage Forms' },
  { key: 'view_analytics', label: 'View Analytics' },
  { key: 'manage_wedding_settings', label: 'Wedding Settings' },
  { key: 'manage_contracts', label: 'Manage Contracts' },
  { key: 'manage_packages', label: 'Manage Packages' },
];

// Default permissions per role
export const ROLE_DEFAULTS: Record<string, Record<string, boolean>> = {
  admin: Object.fromEntries(ALL_PERMISSIONS.map((p) => [p.key, true])),
  editor: {
    manage_guests: true, manage_budget: true, manage_gallery: true, manage_seating: true,
    manage_vendors: false, send_rsvp: false, send_reminders: false, manage_forms: true,
    view_analytics: true, manage_wedding_settings: false, manage_contracts: false, manage_packages: false,
  },
  viewer: {
    manage_guests: false, manage_budget: false, manage_gallery: false, manage_seating: false,
    manage_vendors: false, send_rsvp: false, send_reminders: false, manage_forms: false,
    view_analytics: true, manage_wedding_settings: false, manage_contracts: false, manage_packages: false,
  },
};
