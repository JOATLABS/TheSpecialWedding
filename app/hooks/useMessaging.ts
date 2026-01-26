/**
 * Messaging hook that combines REST API calls with real-time Soketi updates.
 *
 * Usage:
 * ```tsx
 * const { messages, sendMessage, isLoading } = useMessaging({
 *   token,
 *   weddingId,
 *   conversationId,
 * });
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  useConversationChannel,
  useUserChannel,
} from './useSoketi';
import {
  ConversationResponse,
  MessageResponse,
  ConversationParticipant,
  ParticipantRole,
} from '@/types/messaging';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

interface UseMessagingOptions {
  token: string;
  weddingId: string;
  conversationId: string;
  enabled?: boolean;
}

interface UseMessagingReturn {
  messages: MessageResponse[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (body: string, file?: File) => Promise<void>;
  loadMore: () => Promise<void>;
  hasMore: boolean;
  typingUsers: string[];
  sendTypingIndicator: (isTyping: boolean) => void;
}

export function useMessaging({
  token,
  weddingId,
  conversationId,
  enabled = true,
}: UseMessagingOptions): UseMessagingReturn {
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const typingTimeoutRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Subscribe to real-time updates
  const { socketId } = useConversationChannel({
    token,
    conversationId,
    enabled,
    onNewMessage: useCallback((message) => {
      setMessages((prev) => {
        // Avoid duplicates
        if (prev.some((m) => m.message_id === message.message_id)) {
          return prev;
        }
        return [...prev, message as MessageResponse];
      });
    }, []),
    onTyping: useCallback((data) => {
      const { user_id, is_typing } = data;

      // Clear existing timeout for this user
      const existingTimeout = typingTimeoutRef.current.get(user_id);
      if (existingTimeout) {
        clearTimeout(existingTimeout);
      }

      if (is_typing) {
        setTypingUsers((prev) =>
          prev.includes(user_id) ? prev : [...prev, user_id]
        );

        // Auto-remove after 3 seconds of no typing updates
        const timeout = setTimeout(() => {
          setTypingUsers((prev) => prev.filter((id) => id !== user_id));
          typingTimeoutRef.current.delete(user_id);
        }, 3000);
        typingTimeoutRef.current.set(user_id, timeout);
      } else {
        setTypingUsers((prev) => prev.filter((id) => id !== user_id));
      }
    }, []),
  });

  // Fetch initial messages
  useEffect(() => {
    if (!enabled || !conversationId) return;

    const fetchMessages = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations/${conversationId}/messages?limit=50`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch messages');
        }

        const data = await response.json();
        setMessages(data.messages || []);
        setCursor(data.next_cursor || null);
        setHasMore(!!data.next_cursor);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    };

    fetchMessages();
  }, [token, weddingId, conversationId, enabled]);

  // Load more messages (pagination)
  const loadMore = useCallback(async () => {
    if (!cursor || isLoading || !hasMore) return;

    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations/${conversationId}/messages?limit=50&cursor=${cursor}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch more messages');
      }

      const data = await response.json();
      setMessages((prev) => [...prev, ...(data.messages || [])]);
      setCursor(data.next_cursor || null);
      setHasMore(!!data.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [cursor, isLoading, hasMore, token, weddingId, conversationId]);

  // Send a message
  const sendMessage = useCallback(
    async (body: string, file?: File) => {
      const formData = new FormData();
      formData.append('body', body);
      if (socketId) {
        formData.append('socket_id', socketId);
      }
      if (file) {
        formData.append('file', file);
      }

      const response = await fetch(
        `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations/${conversationId}/messages`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send message');
      }

      const message = await response.json();

      // Optimistically add to local state (socket will also deliver, but we check for duplicates)
      setMessages((prev) => {
        if (prev.some((m) => m.message_id === message.message_id)) {
          return prev;
        }
        return [...prev, message];
      });
    },
    [token, weddingId, conversationId, socketId]
  );

  // Send typing indicator
  const sendTypingIndicator = useCallback(
    async (isTyping: boolean) => {
      try {
        await fetch(
          `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations/${conversationId}/typing`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              is_typing: isTyping,
              socket_id: socketId,
            }),
          }
        );
      } catch {
        // Typing indicators are best-effort, don't throw
      }
    },
    [token, weddingId, conversationId, socketId]
  );

  // Cleanup typing timeouts on unmount
  useEffect(() => {
    return () => {
      typingTimeoutRef.current.forEach((timeout) => clearTimeout(timeout));
      typingTimeoutRef.current.clear();
    };
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    loadMore,
    hasMore,
    typingUsers,
    sendTypingIndicator,
  };
}

interface UseConversationsOptions {
  token: string;
  weddingId: string;
  userId: string;
  enabled?: boolean;
}

interface UseConversationsReturn {
  conversations: ConversationResponse[];
  isLoading: boolean;
  error: string | null;
  createConversation: (
    subject: string,
    participants: Array<{ user_id: string; role: ParticipantRole }>
  ) => Promise<ConversationResponse>;
  refresh: () => Promise<void>;
}

export function useConversations({
  token,
  weddingId,
  userId,
  enabled = true,
}: UseConversationsOptions): UseConversationsReturn {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Subscribe to user notifications for new conversations
  useUserChannel({
    token,
    userId,
    enabled,
    onConversationCreated: useCallback((data) => {
      // Fetch the full conversation data
      fetch(
        `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations/${data.conversation_id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
        .then((res) => res.json())
        .then((conversation) => {
          setConversations((prev) => {
            if (prev.some((c) => c.conversation_id === conversation.conversation_id)) {
              return prev;
            }
            return [conversation, ...prev];
          });
        })
        .catch(console.error);
    }, [token, weddingId]),
  });

  // Fetch initial conversations
  const fetchConversations = useCallback(async () => {
    if (!enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations?limit=50`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch conversations');
      }

      const data = await response.json();
      setConversations(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [token, weddingId, enabled]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Create a new conversation
  const createConversation = useCallback(
    async (
      subject: string,
      participants: Array<{ user_id: string; role: ParticipantRole }>
    ): Promise<ConversationResponse> => {
      const response = await fetch(
        `${API_BASE_URL}/messaging/weddings/${weddingId}/conversations`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            wedding_id: weddingId,
            subject,
            participants: participants.map((p) => ({
              user_id: p.user_id,
              role: p.role,
            })),
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create conversation');
      }

      const conversation = await response.json();

      // Add to local state
      setConversations((prev) => [conversation, ...prev]);

      return conversation;
    },
    [token, weddingId]
  );

  return {
    conversations,
    isLoading,
    error,
    createConversation,
    refresh: fetchConversations,
  };
}
