export interface CouplePushStatusPayload {
  enabled?: boolean;
  subscribed?: boolean;
  vapid_public_key?: string | null;
  reason?: string | null;
  subscription_count?: number;
}

export interface CouplePushConfig {
  enabled: boolean;
  subscribed: boolean;
  vapidPublicKey: string | null;
  reason: string | null;
  subscriptionCount: number | null;
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const normalized = base64String.trim();
  if (!normalized) {
    throw new Error('VAPID public key is required');
  }

  const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
  const base64 = `${normalized}${padding}`.replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index);
  }

  return outputArray;
}

export function resolveCouplePushConfig(payload: CouplePushStatusPayload | null | undefined): CouplePushConfig {
  const vapidPublicKey = typeof payload?.vapid_public_key === 'string' && payload.vapid_public_key.trim()
    ? payload.vapid_public_key.trim()
    : null;

  return {
    enabled: payload?.enabled === true,
    subscribed: payload?.subscribed === true,
    vapidPublicKey,
    reason: typeof payload?.reason === 'string' && payload.reason.trim() ? payload.reason.trim() : null,
    subscriptionCount: typeof payload?.subscription_count === 'number' ? payload.subscription_count : null,
  };
}
