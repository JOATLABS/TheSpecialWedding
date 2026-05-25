import type { WeddingEvent } from '@/types/wedding';

export const ALL_WEDDING_EVENTS = 'all';
export const ALL_WEDDING_EVENTS_OPTION = { value: ALL_WEDDING_EVENTS, label: 'All' } as const;

export const BUILT_IN_WEDDING_EVENT_OPTIONS = [
  { value: 'traditional', label: 'Traditional Ceremony' },
  { value: 'white_wedding', label: 'White Wedding' },
  { value: 'reception', label: 'Reception' },
  { value: 'engagement', label: 'Engagement Party' },
  { value: 'rehearsal', label: 'Rehearsal Dinner' },
] as const;

export const WEDDING_EVENT_SELECT_OPTIONS = [
  ...BUILT_IN_WEDDING_EVENT_OPTIONS,
  { value: 'other', label: 'Other' },
] as const;

type BuiltInWeddingEventType = (typeof BUILT_IN_WEDDING_EVENT_OPTIONS)[number]['value'];

const BUILT_IN_EVENT_LABELS = Object.fromEntries(
  BUILT_IN_WEDDING_EVENT_OPTIONS.map((option) => [option.value, option.label])
) as Record<BuiltInWeddingEventType, string>;

const BUILT_IN_EVENT_TYPES = new Set<string>(
  BUILT_IN_WEDDING_EVENT_OPTIONS.map((option) => option.value)
);

function humanizeEventType(value: string): string {
  return value
    .replace(/^custom_/, '')
    .replace(/_[a-z0-9]{6,}$/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function isBuiltInWeddingEventType(type?: string): type is BuiltInWeddingEventType {
  return !!type && BUILT_IN_EVENT_TYPES.has(type);
}

export function getWeddingEventLabel(type?: string, customTypeLabel?: string): string {
  if (type === ALL_WEDDING_EVENTS) {
    return 'All Events';
  }

  if (customTypeLabel?.trim()) {
    return customTypeLabel.trim();
  }

  if (!type) {
    return 'Custom Event';
  }

  if (isBuiltInWeddingEventType(type)) {
    return BUILT_IN_EVENT_LABELS[type];
  }

  return humanizeEventType(type);
}

export function getWeddingEventSelectValue(event: Pick<WeddingEvent, 'type' | 'custom_type_label'>): string {
  return isBuiltInWeddingEventType(event.type) ? event.type : 'other';
}

export function createCustomWeddingEventTypeKey(label: string): string {
  const normalized = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);

  const slug = normalized || 'event';
  const suffix = Math.random().toString(36).slice(2, 8);

  return `custom_${slug}_${suffix}`;
}

export function getWeddingEventOptions(
  events?: Array<Pick<WeddingEvent, 'type' | 'custom_type_label'>>
): Array<{ value: string; label: string }> {
  if (!events?.length) {
    return [...BUILT_IN_WEDDING_EVENT_OPTIONS];
  }

  const seen = new Set<string>();
  const options: Array<{ value: string; label: string }> = [];

  for (const event of events) {
    if (!event?.type || seen.has(event.type)) {
      continue;
    }

    seen.add(event.type);
    options.push({
      value: event.type,
      label: getWeddingEventLabel(event.type, event.custom_type_label),
    });
  }

  return options;
}
