export type PlanFeatureState = Record<string, boolean>;

export interface PlanFeatureOption {
  key: string;
  label: string;
  description?: string;
}

export const STOREFRONT_PLAN_FEATURE_OPTIONS = [
  {
    key: 'planner_storefront',
    label: 'Planner storefront',
    description:
      'Allows planners on this plan to design, preview, publish, and share a storefront on the platform URL.',
  },
  {
    key: 'custom_domain',
    label: 'Custom domain',
    description:
      'Allows planners on this plan to start or replace custom-domain setup; existing-domain management remains separately protected.',
  },
] as const satisfies readonly PlanFeatureOption[];

export const GENERAL_PLAN_FEATURE_OPTIONS: PlanFeatureOption[] = [
  { key: 'guest_management', label: 'Guest management' },
  { key: 'email_invitations', label: 'Email invitations' },
  { key: 'wedding_website', label: 'Wedding website' },
  { key: 'timeline_builder', label: 'Timeline builder' },
  { key: 'basic_analytics', label: 'Basic analytics' },
  { key: 'advanced_analytics', label: 'Advanced analytics' },
  { key: 'vendor_management', label: 'Vendor management' },
  { key: 'seating_orchestration', label: 'Seating orchestration' },
  { key: 'ai_features', label: 'AI features' },
  { key: 'ai_tools', label: 'AI tools' },
  { key: 'qr_checkin', label: 'QR check-in' },
  { key: 'guest_memories', label: 'Guest memories' },
  { key: 'automated_reminders', label: 'Automated reminders' },
  { key: 'vendor_collaboration', label: 'Vendor collaboration' },
  { key: 'priority_support', label: 'Priority support' },
  { key: 'white_label', label: 'White label' },
  { key: 'api_access', label: 'API access' },
  { key: 'dedicated_support', label: 'Dedicated support' },
  { key: 'custom_integrations', label: 'Custom integrations' },
  { key: 'multi_user_collaboration', label: 'Multi-user collaboration' },
  { key: 'basic_website_builder', label: 'Basic website builder' },
  { key: 'rsvp_system', label: 'RSVP system' },
];

export const PLAN_FEATURE_OPTIONS: PlanFeatureOption[] = [
  ...STOREFRONT_PLAN_FEATURE_OPTIONS,
  ...GENERAL_PLAN_FEATURE_OPTIONS,
];

const STOREFRONT_PLAN_FEATURE_KEYS = new Set<string>(
  STOREFRONT_PLAN_FEATURE_OPTIONS.map((option) => option.key),
);

const PLAN_FEATURE_LABELS = new Map(
  PLAN_FEATURE_OPTIONS.map((option) => [option.key, option.label]),
);

export function humanizeFeatureKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getPlanFeatureLabel(key: string): string {
  return PLAN_FEATURE_LABELS.get(key) ?? humanizeFeatureKey(key);
}

export function buildPlanFeatureState(features?: PlanFeatureState | null): PlanFeatureState {
  const state: PlanFeatureState = {};

  for (const option of PLAN_FEATURE_OPTIONS) {
    state[option.key] = false;
  }

  for (const [key, value] of Object.entries(features ?? {})) {
    state[key] = Boolean(value);
  }

  return state;
}

export function getPlanFeatureEntries(features: PlanFeatureState): PlanFeatureOption[] {
  const knownKeys = new Set(PLAN_FEATURE_OPTIONS.map((option) => option.key));
  const knownEntries = PLAN_FEATURE_OPTIONS.filter((option) => option.key in features);
  const extraEntries = Object.keys(features)
    .filter((key) => !knownKeys.has(key))
    .sort()
    .map((key) => ({ key, label: getPlanFeatureLabel(key) }));

  return [...knownEntries, ...extraEntries];
}

export function getGeneralPlanFeatureEntries(
  features: PlanFeatureState,
): PlanFeatureOption[] {
  return getPlanFeatureEntries(features).filter(
    (entry) => !STOREFRONT_PLAN_FEATURE_KEYS.has(entry.key),
  );
}

export function formatFeatureListInput(featuresList?: string[] | null): string {
  return (featuresList ?? []).join('\n');
}

export function parseFeatureListInput(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}
