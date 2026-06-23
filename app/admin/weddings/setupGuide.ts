import type { Wedding } from '@/types/wedding';

export const WEDDING_SETUP_TABS = [
  'events',
  'vendors',
  'rsvp',
  'privacy',
  'registry',
  'faq',
  'theme',
  'story',
  'couple',
] as const;

export type WeddingSetupTab = (typeof WEDDING_SETUP_TABS)[number];

export type WeddingSetupStatus = 'complete' | 'attention' | 'optional';

export interface WeddingSetupStep {
  id: string;
  tab: WeddingSetupTab;
  title: string;
  description: string;
  actionLabel: string;
  required: boolean;
  status: WeddingSetupStatus;
  statusLabel: string;
}

export interface WeddingSetupSummary {
  steps: WeddingSetupStep[];
  requiredTotal: number;
  requiredComplete: number;
  progressPercent: number;
  nextStep: WeddingSetupStep | null;
}

interface WeddingSetupOptions {
  canViewCoupleTab: boolean;
  vendorAssignmentCount?: number | null;
}

const hasText = (value: unknown) =>
  typeof value === 'string' && value.trim().length > 0;

const hasValidHex = (value: unknown) =>
  typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value.trim());

export const isWeddingSetupTab = (
  value: string | null | undefined,
): value is WeddingSetupTab =>
  typeof value === 'string' &&
  WEDDING_SETUP_TABS.includes(value as WeddingSetupTab);

const makeStep = (
  step: Omit<WeddingSetupStep, 'status' | 'statusLabel'>,
  isComplete: boolean,
): WeddingSetupStep => {
  if (isComplete) {
    return {
      ...step,
      status: 'complete',
      statusLabel: 'Ready',
    };
  }

  return {
    ...step,
    status: step.required ? 'attention' : 'optional',
    statusLabel: step.required ? 'Needs setup' : 'Optional',
  };
};

const eventHasGuestFacingDetails = (event: Wedding['events'][number]) =>
  hasText(event.date) &&
  hasText(event.details?.time) &&
  (hasText(event.details?.venue_name) || hasText(event.details?.location));

export function buildWeddingSetupSummary(
  wedding: Wedding,
  options: WeddingSetupOptions,
): WeddingSetupSummary {
  const eventsReady =
    Array.isArray(wedding.events) &&
    wedding.events.length > 0 &&
    wedding.events.every(eventHasGuestFacingDetails);

  const privacyMode = wedding.privacy_settings?.privacy_mode;
  const privacyReady =
    privacyMode === 'public' ||
    privacyMode === 'private' ||
    (privacyMode === 'password' &&
      hasText(wedding.privacy_settings?.password_protection));

  const rsvpConfig = wedding.rsvp_config;
  const rsvpPhoneNumbers = Array.isArray(rsvpConfig?.phone_numbers)
    ? rsvpConfig.phone_numbers
    : [];
  const rsvpReady = Boolean(
    rsvpConfig &&
      hasText(rsvpConfig.greeting) &&
      hasText(rsvpConfig.help_text) &&
      hasText(rsvpConfig.help_button_label || 'Get Help') &&
      (rsvpConfig.hide_phone_numbers !== false ||
        rsvpPhoneNumbers.some(hasText)),
  );

  const theme = wedding.theme_config;
  const themeReady = Boolean(
    theme &&
      hasValidHex(theme.primary_color) &&
      hasValidHex(theme.secondary_color) &&
      hasValidHex(theme.accent_color) &&
      theme.background_style &&
      theme.font_style,
  );

  const registryReady = Boolean(
    wedding.registries?.some(
      (registry) => hasText(registry.name) && hasText(registry.url),
    ),
  );

  const faqReady = Boolean(
    wedding.faqs?.some((faq) => hasText(faq.question) && hasText(faq.answer)),
  );

  const storyReady = Boolean(
    hasText(wedding.our_story?.text) ||
      hasText(wedding.our_story?.image_url) ||
      wedding.wedding_party?.some((member) => hasText(member.name)),
  );

  const vendorReady = (options.vendorAssignmentCount ?? 0) > 0;

  const steps: WeddingSetupStep[] = [
    makeStep(
      {
        id: 'events',
        tab: 'events',
        title: 'Schedule',
        description: 'Dates, times, venues, and attire guests will see.',
        actionLabel: eventsReady ? 'Review events' : 'Add event details',
        required: true,
      },
      eventsReady,
    ),
    makeStep(
      {
        id: 'vendors',
        tab: 'vendors',
        title: 'Vendors',
        description: 'Assigned vendors, contracts, quotes, and payments.',
        actionLabel: vendorReady ? 'Review vendors' : 'Open vendors',
        required: false,
      },
      vendorReady,
    ),
    makeStep(
      {
        id: 'rsvp',
        tab: 'rsvp',
        title: 'RSVP',
        description: 'Guest-facing RSVP copy and help handoff.',
        actionLabel: rsvpReady ? 'Review RSVP' : 'Finish RSVP copy',
        required: true,
      },
      rsvpReady,
    ),
    makeStep(
      {
        id: 'privacy',
        tab: 'privacy',
        title: 'Access',
        description: 'Public, private, or password-protected access.',
        actionLabel: privacyReady ? 'Review access' : 'Choose access mode',
        required: true,
      },
      privacyReady,
    ),
    makeStep(
      {
        id: 'registry',
        tab: 'registry',
        title: 'Registry',
        description: 'Gift registry links shown on the wedding site.',
        actionLabel: registryReady ? 'Review registry' : 'Add registry',
        required: false,
      },
      registryReady,
    ),
    makeStep(
      {
        id: 'faq',
        tab: 'faq',
        title: 'FAQ',
        description: 'Travel, dress code, hotel, and guest questions.',
        actionLabel: faqReady ? 'Review FAQ' : 'Add FAQ',
        required: false,
      },
      faqReady,
    ),
    makeStep(
      {
        id: 'theme',
        tab: 'theme',
        title: 'Theme',
        description: 'Colors, typography, and public page styling.',
        actionLabel: themeReady ? 'Review theme' : 'Set theme',
        required: true,
      },
      themeReady,
    ),
    makeStep(
      {
        id: 'story',
        tab: 'story',
        title: 'Story',
        description: 'Couple story, photos, and wedding party.',
        actionLabel: storyReady ? 'Review story' : 'Add story',
        required: false,
      },
      storyReady,
    ),
  ];

  if (options.canViewCoupleTab) {
    steps.push(
      makeStep(
        {
          id: 'couple',
          tab: 'couple',
          title: 'Couple Portal',
          description: 'Couple access, messaging, and digest settings.',
          actionLabel: 'Manage access',
          required: false,
        },
        false,
      ),
    );
  }

  const requiredSteps = steps.filter((step) => step.required);
  const requiredComplete = requiredSteps.filter(
    (step) => step.status === 'complete',
  ).length;

  return {
    steps,
    requiredTotal: requiredSteps.length,
    requiredComplete,
    progressPercent:
      requiredSteps.length === 0
        ? 100
        : Math.round((requiredComplete / requiredSteps.length) * 100),
    nextStep:
      requiredSteps.find((step) => step.status === 'attention') ?? null,
  };
}
