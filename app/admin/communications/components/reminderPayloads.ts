export interface EventReminderEmailPayloadInput {
  weddingSlug: string;
  eventType: string;
  customMessage: string;
  emailSubject: string;
  targetGroup: string;
}

export interface EventReminderEmailPayload {
  wedding_slug: string;
  event_type: string;
  custom_subject: string | null;
  custom_html: string | null;
  target_group: string;
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function buildEventReminderEmailPayload({
  weddingSlug,
  eventType,
  customMessage,
  emailSubject,
  targetGroup,
}: EventReminderEmailPayloadInput): EventReminderEmailPayload {
  return {
    wedding_slug: weddingSlug,
    event_type: eventType,
    custom_subject: optionalText(emailSubject),
    custom_html: optionalText(customMessage),
    target_group: targetGroup,
  };
}
