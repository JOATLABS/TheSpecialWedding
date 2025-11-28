
import React, { useState, useEffect, useCallback } from 'react';
import Inbox from './Inbox';
import ConversationView from './ConversationView';
import Composer from './Composer';
import { ConversationResponse, MessageResponse } from '../../models/messaging';

const Messaging = () => {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [socket, setSocket] = useState<WebSocket | null>(null);

  const weddingId = "1"; // This should be dynamic based on the user's context

  const fetchConversations = useCallback(async () => {
    try {
      const response = await fetch(`/api/messaging/weddings/${weddingId}/conversations`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data.items);
        if (data.items.length > 0) {
          setActiveConversation(data.items[0]);
        }
      }
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
    }
  }, [weddingId]);

  const fetchMessages = useCallback(async (conversationId: string) => {
    try {
      const response = await fetch(`/api/messaging/weddings/${weddingId}/conversations/${conversationId}/messages`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    }
  }, [weddingId]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation.conversation_id);

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/messaging/ws/${activeConversation.conversation_id}`;
      const ws = new WebSocket(wsUrl);
      setSocket(ws);

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        setMessages((prevMessages) => [...prevMessages, message]);
      };

      return () => {
        ws.close();
      };
    }
  }, [activeConversation, fetchMessages]);

  const handleSendMessage = async (message: string) => {
    if (activeConversation) {
      try {
        await fetch(`/api/messaging/weddings/${weddingId}/conversations/${activeConversation.conversation_id}/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ body: message }),
        });
      } catch (error) {
        console.error("Failed to send message:", error);
      }
    }
  };

  return (
    <div className="flex h-screen">
      <Inbox conversations={conversations} onSelectConversation={setActiveConversation} />
      <div className="flex flex-col flex-1">
        <ConversationView messages={messages} />
        <Composer onSendMessage={handleSendMessage} />
      </div>
    </div>
  );
};

export default Messaging;
