/**
 * Soketi/Pusher client hook for real-time messaging.
 *
 * This hook provides a battle-tested WebSocket connection via Pusher-js,
 * which connects to Soketi (self-hosted Pusher replacement).
 *
 * Security:
 * - All channel subscriptions require server-side auth via /messaging/pusher/auth
 * - Private channels (private-*) require the user to be authenticated
 * - Presence channels (presence-*) track who's online
 * - The server validates access before generating auth tokens
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import Pusher, { Channel, PresenceChannel } from 'pusher-js';

// Soketi configuration from environment
const SOKETI_KEY = process.env.NEXT_PUBLIC_SOKETI_KEY || 'app-key';
const SOKETI_HOST = process.env.NEXT_PUBLIC_SOKETI_HOST || 'localhost';
const SOKETI_PORT = parseInt(process.env.NEXT_PUBLIC_SOKETI_PORT || '6001', 10);
const SOKETI_USE_TLS = process.env.NEXT_PUBLIC_SOKETI_USE_TLS === 'true';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

// Singleton Pusher instance
let pusherInstance: Pusher | null = null;

function getPusherInstance(token: string): Pusher {
  if (pusherInstance) {
    return pusherInstance;
  }

  pusherInstance = new Pusher(SOKETI_KEY, {
    wsHost: SOKETI_HOST,
    wsPort: SOKETI_PORT,
    wssPort: SOKETI_PORT,
    forceTLS: SOKETI_USE_TLS,
    enabledTransports: ['ws', 'wss'],
    disableStats: true,
    cluster: 'mt1', // Required by pusher-js but ignored by Soketi
    authEndpoint: `${API_BASE_URL}/messaging/pusher/auth`,
    auth: {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  });

  // Connection state logging
  pusherInstance.connection.bind('connected', () => {
    console.log('[Soketi] Connected');
  });

  pusherInstance.connection.bind('disconnected', () => {
    console.log('[Soketi] Disconnected');
  });

  pusherInstance.connection.bind('error', (error: Error) => {
    console.error('[Soketi] Connection error:', error);
  });

  return pusherInstance;
}

export function updatePusherAuth(token: string): void {
  if (pusherInstance) {
    pusherInstance.config.auth = {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    };
  }
}

export function disconnectPusher(): void {
  if (pusherInstance) {
    pusherInstance.disconnect();
    pusherInstance = null;
  }
}

interface UseSoketiOptions {
  token: string;
  enabled?: boolean;
}

interface UseSoketiReturn {
  pusher: Pusher | null;
  connectionState: string;
  subscribe: (channelName: string) => Channel | null;
  unsubscribe: (channelName: string) => void;
}

/**
 * Hook to access the Soketi/Pusher connection.
 */
export function useSoketi({ token, enabled = true }: UseSoketiOptions): UseSoketiReturn {
  const [connectionState, setConnectionState] = useState<string>('disconnected');
  const pusherRef = useRef<Pusher | null>(null);

  useEffect(() => {
    if (!enabled || !token) {
      return;
    }

    const pusher = getPusherInstance(token);
    pusherRef.current = pusher;

    const handleStateChange = (states: { current: string }) => {
      setConnectionState(states.current);
    };

    pusher.connection.bind('state_change', handleStateChange);
    setConnectionState(pusher.connection.state);

    return () => {
      pusher.connection.unbind('state_change', handleStateChange);
    };
  }, [token, enabled]);

  const subscribe = useCallback((channelName: string): Channel | null => {
    if (!pusherRef.current) return null;
    return pusherRef.current.subscribe(channelName);
  }, []);

  const unsubscribe = useCallback((channelName: string): void => {
    if (!pusherRef.current) return;
    pusherRef.current.unsubscribe(channelName);
  }, []);

  return {
    pusher: pusherRef.current,
    connectionState,
    subscribe,
    unsubscribe,
  };
}

interface UseConversationChannelOptions {
  token: string;
  conversationId: string;
  enabled?: boolean;
  onNewMessage?: (message: MessageEvent) => void;
  onReadReceipt?: (receipt: ReadReceiptEvent) => void;
  onTyping?: (typing: TypingEvent) => void;
}

interface MessageEvent {
  message_id: string;
  conversation_id: string;
  sender_id: string;
  sender_role: string;
  body: string;
  created_at: string;
  attachments: Array<{
    type: string;
    url?: string;
    title?: string;
  }>;
  linked_resource?: {
    resource_type: string;
    resource_id: string;
    title?: string;
  };
}

interface ReadReceiptEvent {
  conversation_id: string;
  participant_id: string;
  last_read_at: string;
}

interface TypingEvent {
  user_id: string;
  is_typing: boolean;
}

/**
 * Hook to subscribe to a conversation channel for real-time updates.
 */
export function useConversationChannel({
  token,
  conversationId,
  enabled = true,
  onNewMessage,
  onReadReceipt,
  onTyping,
}: UseConversationChannelOptions): { socketId: string | null } {
  const { pusher } = useSoketi({ token, enabled });
  const [socketId, setSocketId] = useState<string | null>(null);

  useEffect(() => {
    if (!pusher || !conversationId || !enabled) {
      return;
    }

    // Get socket ID for excluding self from broadcasts
    setSocketId(pusher.connection.socket_id);

    const channelName = `private-conversation-${conversationId}`;
    const channel = pusher.subscribe(channelName);

    channel.bind('new-message', (data: MessageEvent) => {
      onNewMessage?.(data);
    });

    channel.bind('read-receipt', (data: ReadReceiptEvent) => {
      onReadReceipt?.(data);
    });

    channel.bind('typing', (data: TypingEvent) => {
      onTyping?.(data);
    });

    channel.bind('pusher:subscription_error', (error: Error) => {
      console.error(`[Soketi] Failed to subscribe to ${channelName}:`, error);
    });

    return () => {
      channel.unbind_all();
      pusher.unsubscribe(channelName);
    };
  }, [pusher, conversationId, enabled, onNewMessage, onReadReceipt, onTyping]);

  return { socketId };
}

interface UseUserChannelOptions {
  token: string;
  userId: string;
  enabled?: boolean;
  onConversationCreated?: (data: ConversationCreatedEvent) => void;
}

interface ConversationCreatedEvent {
  conversation_id: string;
  subject?: string;
  wedding_id?: string;
  created_by: string;
}

/**
 * Hook to subscribe to user-specific notifications.
 */
export function useUserChannel({
  token,
  userId,
  enabled = true,
  onConversationCreated,
}: UseUserChannelOptions): void {
  const { pusher } = useSoketi({ token, enabled });

  useEffect(() => {
    if (!pusher || !userId || !enabled) {
      return;
    }

    const channelName = `private-user-${userId}`;
    const channel = pusher.subscribe(channelName);

    channel.bind('conversation-created', (data: ConversationCreatedEvent) => {
      onConversationCreated?.(data);
    });

    channel.bind('pusher:subscription_error', (error: Error) => {
      console.error(`[Soketi] Failed to subscribe to ${channelName}:`, error);
    });

    return () => {
      channel.unbind_all();
      pusher.unsubscribe(channelName);
    };
  }, [pusher, userId, enabled, onConversationCreated]);
}

interface PresenceMember {
  id: string;
  info: {
    role: string;
  };
}

interface UsePresenceChannelOptions {
  token: string;
  conversationId: string;
  enabled?: boolean;
  onMemberAdded?: (member: PresenceMember) => void;
  onMemberRemoved?: (member: PresenceMember) => void;
}

interface UsePresenceChannelReturn {
  members: PresenceMember[];
  me: PresenceMember | null;
}

/**
 * Hook for presence channel to track who's online in a conversation.
 */
export function usePresenceChannel({
  token,
  conversationId,
  enabled = true,
  onMemberAdded,
  onMemberRemoved,
}: UsePresenceChannelOptions): UsePresenceChannelReturn {
  const { pusher } = useSoketi({ token, enabled });
  const [members, setMembers] = useState<PresenceMember[]>([]);
  const [me, setMe] = useState<PresenceMember | null>(null);

  useEffect(() => {
    if (!pusher || !conversationId || !enabled) {
      return;
    }

    const channelName = `presence-conversation-${conversationId}`;
    const channel = pusher.subscribe(channelName) as PresenceChannel;

    channel.bind('pusher:subscription_succeeded', (members: { members: Record<string, PresenceMember['info']>; me: { id: string; info: PresenceMember['info'] } }) => {
      const memberList = Object.entries(members.members).map(([id, info]) => ({
        id,
        info,
      }));
      setMembers(memberList);
      setMe({ id: members.me.id, info: members.me.info });
    });

    channel.bind('pusher:member_added', (member: PresenceMember) => {
      setMembers((prev) => [...prev, member]);
      onMemberAdded?.(member);
    });

    channel.bind('pusher:member_removed', (member: PresenceMember) => {
      setMembers((prev) => prev.filter((m) => m.id !== member.id));
      onMemberRemoved?.(member);
    });

    channel.bind('pusher:subscription_error', (error: Error) => {
      console.error(`[Soketi] Failed to subscribe to ${channelName}:`, error);
    });

    return () => {
      channel.unbind_all();
      pusher.unsubscribe(channelName);
    };
  }, [pusher, conversationId, enabled, onMemberAdded, onMemberRemoved]);

  return { members, me };
}
