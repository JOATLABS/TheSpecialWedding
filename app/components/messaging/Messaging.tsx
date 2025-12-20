
import React, { useState, useEffect, useCallback } from 'react';
import Inbox from './Inbox';
import ConversationView from './ConversationView';
import Composer from './Composer';
import { ConversationResponse, MessageResponse } from '../../types/messaging';

interface MessagingProps {
  weddingId: string;
}

const Messaging: React.FC<MessagingProps> = ({ weddingId }) => {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [socket, setSocket] = useState<WebSocket | null>(null);

  const fetchConversations = useCallback(async () => {
    const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
    if (!token) {
      console.error("No auth token found");
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/messaging/weddings/${weddingId}/conversations`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
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
    const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
    if (!token) {
      console.error("No auth token found");
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/messaging/weddings/${weddingId}/conversations/${conversationId}/messages`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
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

      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      if (!token) {
        console.error("No auth token found");
        return;
      }

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const wsUrl = `${baseUrl.replace(/^http/, 'ws')}/messaging/ws/${activeConversation.conversation_id}?token=${token}`;
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

  const handleSendMessage = async (message: string, file?: File) => {
    const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
    if (!token) {
      console.error("No auth token found");
      return;
    }

    if (activeConversation) {
      const formData = new FormData();
      formData.append('body', message);
      if (file) {
        formData.append('file', file);
      }

      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
        await fetch(`${baseUrl}/messaging/weddings/${weddingId}/conversations/${activeConversation.conversation_id}/messages`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          body: formData,
        });
      } catch (error) {
        console.error("Failed to send message:", error);
      }
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <Inbox
        conversations={conversations}
        onSelectConversation={setActiveConversation}
        activeConversationId={activeConversation?.conversation_id}
      />
      <div className="flex flex-col flex-1">
        {activeConversation ? (
          <>
            <ConversationView messages={messages} activeConversation={activeConversation} />
            <Composer onSendMessage={handleSendMessage} />
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500">Select a conversation to start messaging</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Messaging;
