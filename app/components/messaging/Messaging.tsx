
import React, { useState, useEffect, useCallback } from 'react';
import Inbox from './Inbox';
import ConversationView from './ConversationView';
import Composer from './Composer';
import { ConversationResponse, MessageResponse, ParticipantRole } from '../../types/messaging';

interface MessagingProps {
  weddingId: string;
}

const Messaging: React.FC<MessagingProps> = ({ weddingId }) => {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [showNewConversation, setShowNewConversation] = useState(false);
  const [newConversationSubject, setNewConversationSubject] = useState('');
  const [newParticipantEmail, setNewParticipantEmail] = useState('');
  const [newParticipantRole, setNewParticipantRole] = useState<ParticipantRole>(ParticipantRole.VENDOR);
  const [isCreating, setIsCreating] = useState(false);
  const [loading, setLoading] = useState(true);

  const getToken = () => localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
  const getCurrentUserEmail = () => {
    const token = getToken();
    if (!token) return null;
    try {
      const payload = token.split('.')[1];
      const decoded = atob(payload);
      const parsed = JSON.parse(decoded);
      return parsed.sub || parsed.email;
    } catch {
      return null;
    }
  };

  const fetchConversations = useCallback(async () => {
    const token = getToken();
    if (!token) {
      console.error("No auth token found");
      setLoading(false);
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
        if (data.items.length > 0 && !activeConversation) {
          setActiveConversation(data.items[0]);
        }
      }
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
    } finally {
      setLoading(false);
    }
  }, [weddingId, activeConversation]);

  const fetchMessages = useCallback(async (conversationId: string) => {
    const token = getToken();
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

  const createConversation = async () => {
    const token = getToken();
    const userEmail = getCurrentUserEmail();
    if (!token || !userEmail) {
      console.error("No auth token found");
      return;
    }

    if (!newConversationSubject.trim() || !newParticipantEmail.trim()) {
      return;
    }

    setIsCreating(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/messaging/weddings/${weddingId}/conversations`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wedding_id: weddingId,
          subject: newConversationSubject.trim(),
          channel: 'chat',
          participants: [
            { user_id: userEmail, role: 'planner' },
            { user_id: newParticipantEmail.trim(), role: newParticipantRole },
          ],
        }),
      });

      if (response.ok) {
        const newConvo = await response.json();
        setConversations(prev => [newConvo, ...prev]);
        setActiveConversation(newConvo);
        setShowNewConversation(false);
        setNewConversationSubject('');
        setNewParticipantEmail('');
      } else {
        console.error("Failed to create conversation");
      }
    } catch (error) {
      console.error("Failed to create conversation:", error);
    } finally {
      setIsCreating(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation.conversation_id);

      const token = getToken();
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
    const token = getToken();
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

  if (loading) {
    return (
      <div className="flex h-screen bg-gray-100 items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading messages...</p>
        </div>
      </div>
    );
  }

  // Empty state / Onboarding
  if (conversations.length === 0 && !showNewConversation) {
    return (
      <div className="flex h-screen bg-gray-100 items-center justify-center">
        <div className="max-w-md text-center p-8 bg-white rounded-xl shadow-lg">
          <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-3">Welcome to Messaging</h2>
          <p className="text-gray-600 mb-6">
            Start conversations with vendors, couples, and wedding party members.
            Keep all your wedding communications in one place.
          </p>
          <div className="space-y-3 text-left mb-6 bg-gray-50 p-4 rounded-lg">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-sm text-gray-700">Chat with vendors about contracts and details</span>
            </div>
            <div className="flex items-start">
              <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-sm text-gray-700">Coordinate with couples on their special day</span>
            </div>
            <div className="flex items-start">
              <svg className="w-5 h-5 text-green-500 mr-3 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-sm text-gray-700">Share files and attachments securely</span>
            </div>
          </div>
          <button
            onClick={() => setShowNewConversation(true)}
            className="w-full bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
          >
            Start Your First Conversation
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Inbox with New Conversation button */}
      <div className="flex flex-col w-full md:w-1/3 lg:w-1/4 border-r border-gray-200 bg-gray-50">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-800">Inbox</h2>
            <button
              onClick={() => setShowNewConversation(true)}
              className="bg-indigo-600 text-white p-2 rounded-lg hover:bg-indigo-700 transition-colors"
              title="New Conversation"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
          <Inbox
            conversations={conversations}
            onSelectConversation={setActiveConversation}
            activeConversationId={activeConversation?.conversation_id}
          />
        </div>
      </div>

      {/* Main content area */}
      <div className="flex flex-col flex-1">
        {activeConversation ? (
          <>
            <ConversationView messages={messages} activeConversation={activeConversation} />
            <Composer onSendMessage={handleSendMessage} />
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-gray-500">Select a conversation to start messaging</p>
            </div>
          </div>
        )}
      </div>

      {/* New Conversation Modal */}
      {showNewConversation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-900">New Conversation</h3>
              <button
                onClick={() => setShowNewConversation(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <input
                  type="text"
                  value={newConversationSubject}
                  onChange={(e) => setNewConversationSubject(e.target.value)}
                  placeholder="e.g., Catering Details, Venue Coordination"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Participant Email</label>
                <input
                  type="email"
                  value={newParticipantEmail}
                  onChange={(e) => setNewParticipantEmail(e.target.value)}
                  placeholder="vendor@example.com"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Participant Role</label>
                <select
                  value={newParticipantRole}
                  onChange={(e) => setNewParticipantRole(e.target.value as ParticipantRole)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value={ParticipantRole.VENDOR}>Vendor</option>
                  <option value={ParticipantRole.COUPLE}>Couple</option>
                  <option value={ParticipantRole.WEDDING_PARTY}>Wedding Party</option>
                </select>
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowNewConversation(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createConversation}
                disabled={isCreating || !newConversationSubject.trim() || !newParticipantEmail.trim()}
                className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCreating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Messaging;
