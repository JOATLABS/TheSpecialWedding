// Shared team management constants
export const ROLES = [
  { value: 'admin', label: 'Admin', desc: 'Full access to everything', color: 'text-rose-700 dark:text-wedding-rose' },
  { value: 'editor', label: 'Editor', desc: 'Create & edit content', color: 'text-teal-700 dark:text-wedding-sage' },
  { value: 'viewer', label: 'Viewer', desc: 'Read-only access', color: 'text-slate-700 dark:text-slate-300' },
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
  { key: 'manage_couple_portal', label: 'Manage Couple Portal' },
  { key: 'message_couples', label: 'Message Couples' },
  { key: 'view_shared_calendar', label: 'View Shared Calendar' },
  { key: 'view_calendar_details', label: 'View Calendar Details' },
  { key: 'connect_personal_calendar', label: 'Connect Personal Calendar' },
  { key: 'manage_calendar_connections', label: 'Manage Calendar Connections' },
  { key: 'schedule_meetings', label: 'Schedule Meetings' },
  { key: 'edit_meetings', label: 'Edit Meetings' },
  { key: 'cancel_meetings', label: 'Cancel Meetings' },
  { key: 'send_meeting_invites', label: 'Send Meeting Invites' },
  { key: 'view_team_availability', label: 'View Team Availability' },
  { key: 'manage_calendar_tasks', label: 'Manage Calendar Tasks' },
  { key: 'sync_calendar_tasks', label: 'Sync Calendar Tasks' },
];

// Default permissions per role
export const ROLE_DEFAULTS: Record<string, Record<string, boolean>> = {
  admin: Object.fromEntries(ALL_PERMISSIONS.map((p) => [p.key, true])),
  editor: {
    manage_guests: true, manage_budget: true, manage_gallery: true, manage_seating: true,
    manage_vendors: false, send_rsvp: false, send_reminders: false, manage_forms: true,
    view_analytics: true, manage_wedding_settings: false, manage_contracts: false, manage_packages: false,
    manage_couple_portal: true, message_couples: false,
    view_shared_calendar: true, view_calendar_details: true, connect_personal_calendar: true,
    manage_calendar_connections: false, schedule_meetings: true, edit_meetings: true,
    cancel_meetings: true, send_meeting_invites: true, view_team_availability: true,
    manage_calendar_tasks: true, sync_calendar_tasks: true,
  },
  viewer: {
    manage_guests: false, manage_budget: false, manage_gallery: false, manage_seating: false,
    manage_vendors: false, send_rsvp: false, send_reminders: false, manage_forms: false,
    view_analytics: true, manage_wedding_settings: false, manage_contracts: false, manage_packages: false,
    manage_couple_portal: false, message_couples: false,
    view_shared_calendar: true, view_calendar_details: false, connect_personal_calendar: false,
    manage_calendar_connections: false, schedule_meetings: false, edit_meetings: false,
    cancel_meetings: false, send_meeting_invites: false, view_team_availability: false,
    manage_calendar_tasks: false, sync_calendar_tasks: false,
  },
};
