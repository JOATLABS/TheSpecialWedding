'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
  MessageCircle,
  X,
  Send,
  Loader2,
  Sparkles,
  AlertCircle,
  ChevronDown,
  Coins
} from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  creditsUsed?: number;
}

interface AIChatWidgetProps {
  weddingId?: string;
  weddingName?: string;
}

export function AIChatWidget({ weddingId, weddingName }: AIChatWidgetProps) {
  const { token } = useAdmin();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creditsRemaining, setCreditsRemaining] = useState<number | null>(null);
  const [creditsWarning, setCreditsWarning] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Fetch initial credits
  useEffect(() => {
    if (token && isOpen) {
      fetchCredits();
    }
  }, [token, isOpen]);

  const fetchCredits = async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/ai/credits`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setCreditsRemaining(data.credits_remaining);
      }
    } catch (err) {
      // Silently fail - not critical
    }
  };

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading || !token) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const baseUrl = getApiBaseUrl();

      // Build conversation history for context
      const conversationHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await fetch(`${baseUrl}/admin/ai/chat`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage.content,
          wedding_id: weddingId || null,
          conversation_history: conversationHistory
        })
      });

      if (response.status === 402) {
        const data = await response.json();
        setError(`Insufficient credits. You need 1 credit but have ${data.detail?.available || 0}.`);
        return;
      }

      if (response.status === 429) {
        setError('Too many requests. Please wait a moment and try again.');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
        creditsUsed: data.credits_used
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Update credits
      if (data.credits_remaining !== undefined) {
        setCreditsRemaining(data.credits_remaining);
      }

      // Show warning if credits are low
      if (data.warning) {
        setCreditsWarning(data.warning);
      }

    } catch (err) {
      setError('Failed to get response. Please try again.');
      toast.error('AI chat failed');
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, token, messages, weddingId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    setCreditsWarning(null);
  };

  // Floating button when closed
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-purple-600 to-indigo-600 text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
        title="Chat with AI Assistant"
      >
        <Sparkles className="h-6 w-6" />
      </button>
    );
  }

  // Chat panel when open
  return (
    <div className="fixed bottom-6 right-6 z-50 flex h-[600px] w-[400px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <div>
            <h3 className="font-semibold">AI Wedding Assistant</h3>
            {weddingName && (
              <p className="text-xs text-purple-200">{weddingName}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {creditsRemaining !== null && (
            <div className="flex items-center gap-1 rounded-full bg-white/20 px-2 py-1 text-xs">
              <Coins className="h-3 w-3" />
              <span>{creditsRemaining} credits</span>
            </div>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="rounded-full p-1 hover:bg-white/20"
            title="Minimize"
          >
            <ChevronDown className="h-5 w-5" />
          </button>
          <button
            onClick={() => { setIsOpen(false); clearChat(); }}
            className="rounded-full p-1 hover:bg-white/20"
            title="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Credits warning */}
      {creditsWarning && (
        <div className="bg-amber-50 px-4 py-2 text-xs text-amber-800 border-b border-amber-100">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <p>{creditsWarning}</p>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-500">
            <Sparkles className="h-12 w-12 mb-4 text-purple-300" />
            <h4 className="font-medium text-gray-700">How can I help you today?</h4>
            <p className="text-sm mt-2 max-w-[280px]">
              Ask me anything about wedding planning, budgets, vendors, or cultural traditions.
            </p>
            {weddingName && (
              <p className="text-xs mt-4 text-purple-600">
                Context: {weddingName}
              </p>
            )}
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-purple-600 text-white rounded-br-md'
                  : 'bg-gray-100 text-gray-800 rounded-bl-md'
              }`}
            >
              <p className="whitespace-pre-wrap text-sm">{message.content}</p>
              <div className={`flex items-center gap-2 mt-1 text-xs ${
                message.role === 'user' ? 'text-purple-200' : 'text-gray-400'
              }`}>
                <span>
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {message.creditsUsed !== undefined && (
                  <span className="flex items-center gap-1">
                    <Coins className="h-3 w-3" />
                    {message.creditsUsed}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex items-center gap-2 text-gray-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="bg-red-50 text-red-700 rounded-lg px-4 py-2 text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about budgets, vendors, traditions..."
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 max-h-24"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-600 text-white transition-colors hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2 text-center">
          1 credit per message
        </p>
      </div>
    </div>
  );
}

export default AIChatWidget;