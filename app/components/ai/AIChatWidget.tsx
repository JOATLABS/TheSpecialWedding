'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { usePathname } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  X,
  Send,
  Loader2,
  Sparkles,
  AlertCircle,
  ChevronDown,
  Coins,
  Heart,
  ChevronUp
} from 'lucide-react';

export function isInboxComposerSurface(pathname: string | null): boolean {
  return pathname === '/admin/inbox' || pathname?.startsWith('/admin/communications/inbox') === true;
}

export function getAIWidgetPositionClasses(pathname: string | null, isOpen: boolean): string {
  if (isInboxComposerSurface(pathname)) {
    return isOpen
      ? 'bottom-24 right-4 sm:right-6'
      : 'bottom-24 right-4 sm:right-6';
  }
  return isOpen ? 'bottom-6 right-4 sm:right-6' : 'bottom-6 right-6';
}

export function getAIWidgetPanelSizeClasses(pathname: string | null): string {
  return isInboxComposerSurface(pathname)
    ? 'h-[min(600px,calc(100svh-8rem))]'
    : 'h-[min(600px,calc(100svh-3rem))]';
}

export function formatAIChatError(message: string): string {
  const trimmed = message.trim().replace(/^AI generation failed:\s*/i, '');
  if (/please try again\.?$/i.test(trimmed)) {
    return trimmed.replace(/\.+$/g, '.');
  }
  return `${trimmed || 'AI chat failed'}. Please try again.`;
}

function AssistantMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-2 leading-relaxed last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-4">{children}</ul>,
        ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-4">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="font-medium underline decoration-slate-400 underline-offset-2"
          >
            {children}
          </a>
        ),
        code: ({ children }) => (
          <code className="rounded bg-white/60 px-1 py-0.5 text-[0.85em] text-slate-800 dark:bg-slate-900/70 dark:text-slate-100">
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="my-2 overflow-x-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
            {children}
          </pre>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  creditsUsed?: number;
}

interface Wedding {
  id: string;
  couple_names: string;
  date: string;
  cultural_style?: string;
  region?: string;
}

interface AIChatWidgetProps {
  weddingId?: string;
  weddingName?: string;
}

// Page context detection
interface PageContext {
  page: string;
  label: string;
  prompts: string[];
  systemHint: string;
}

const PAGE_CONTEXTS: Record<string, PageContext> = {
  // Contract Canvas - Creating new contracts
  'contracts/new': {
    page: 'contract_canvas',
    label: 'Contract Canvas',
    prompts: [
      "Write a cancellation policy clause",
      "Suggest payment milestones for this vendor",
      "What terms should I include for deposits?"
    ],
    systemHint: "User is creating a vendor contract in the Contract Canvas. Help write professional contract clauses, suggest payment terms based on vendor type, and provide legal considerations for wedding vendor agreements."
  },
  // Contracts Management
  'vendors/contracts': {
    page: 'contracts',
    label: 'Contracts',
    prompts: [
      "Review my pending contracts",
      "What's the standard deposit percentage?",
      "Help me follow up on unsigned contracts"
    ],
    systemHint: "User is managing vendor contracts. Help track contract status, suggest follow-up strategies, and provide industry-standard terms."
  },
  // Budget Tracker
  'budget': {
    page: 'budget',
    label: 'Budget',
    prompts: [
      "Analyze my budget allocation",
      "Where can I cut costs without sacrificing quality?",
      "Am I overspending on any category?"
    ],
    systemHint: "User is working on wedding budget. Analyze spending patterns, suggest cost optimizations, provide typical budget breakdowns for their wedding size and cultural style."
  },
  // Calendar & Timeline
  'planner/calendar': {
    page: 'calendar',
    label: 'Calendar',
    prompts: [
      "What should I focus on this week?",
      "Generate a planning timeline for the next month",
      "What tasks am I behind on?"
    ],
    systemHint: "User is viewing their planning calendar. Help prioritize tasks, suggest timeline milestones based on wedding date, and identify scheduling conflicts."
  },
  // Guest Management
  'guests': {
    page: 'guests',
    label: 'Guests',
    prompts: [
      "Draft an RSVP reminder message",
      "How should I handle plus-ones?",
      "Suggest seating arrangements"
    ],
    systemHint: "User is managing the guest list. Help with RSVP tracking, guest communication templates, seating arrangement strategies, and plus-one policies."
  },
  // Gallery & Photos
  'gallery': {
    page: 'gallery',
    label: 'Gallery',
    prompts: [
      "How should I organize wedding photos?",
      "Tips for sharing photos with guests",
      "Photo timeline for the wedding day"
    ],
    systemHint: "User is managing wedding gallery and photos. Help with photo organization, sharing strategies, and shot list recommendations."
  },
  // Vendor Directory
  'vendors': {
    page: 'vendors',
    label: 'Vendors',
    prompts: [
      "Questions to ask this type of vendor",
      "How to compare vendor quotes fairly",
      "Red flags when hiring vendors"
    ],
    systemHint: "User is managing their vendor directory. Help with vendor selection criteria, negotiation tactics, and questions to ask different vendor types."
  },
  // Forms
  'forms': {
    page: 'forms',
    label: 'Forms',
    prompts: [
      "What questions should I ask in an RSVP form?",
      "Create a vendor questionnaire",
      "Dietary restriction form questions"
    ],
    systemHint: "User is creating or managing forms. Help design effective questionnaires for RSVPs, vendor intake, dietary restrictions, and guest preferences."
  },
  // Reminders & Communications
  'reminders': {
    page: 'reminders',
    label: 'Reminders',
    prompts: [
      "Draft a friendly RSVP reminder",
      "When should I send each reminder?",
      "Write a vendor payment reminder"
    ],
    systemHint: "User is setting up email/SMS reminders. Help craft professional yet warm communication templates, suggest optimal timing for different reminder types."
  },
  // Money & Payments
  'money': {
    page: 'money',
    label: 'Payments',
    prompts: [
      "Review my payment schedule",
      "Which vendor payments are coming due?",
      "How to handle late payments professionally"
    ],
    systemHint: "User is managing payments and financial transactions. Help track payment schedules, suggest collection strategies, and provide payment reminder templates."
  },
  // Packages (for couples)
  'packages': {
    page: 'packages',
    label: 'Packages',
    prompts: [
      "How should I price my packages?",
      "What services should I bundle together?",
      "Package description templates"
    ],
    systemHint: "User is creating or managing service packages. Help with pricing strategies, service bundling, and compelling package descriptions."
  },
  // Wedding Details Page
  'weddings/': {
    page: 'wedding_details',
    label: 'Wedding Details',
    prompts: [
      "What details am I missing?",
      "Checklist for this wedding",
      "Timeline recommendations"
    ],
    systemHint: "User is viewing a specific wedding's details. Provide tailored advice based on the wedding date, cultural style, guest count, and budget."
  },
  // Main Dashboard
  'planner': {
    page: 'dashboard',
    label: 'Dashboard',
    prompts: [
      "What should I prioritize today?",
      "Give me a status summary across all weddings",
      "Any urgent items needing attention?"
    ],
    systemHint: "User is on the main planner dashboard. Provide overview insights, priority recommendations, and highlight any items needing immediate attention."
  },
  // Notifications
  'notifications': {
    page: 'notifications',
    label: 'Notifications',
    prompts: [
      "What notifications need my attention?",
      "How should I respond to this?",
      "Draft a response"
    ],
    systemHint: "User is viewing notifications. Help prioritize and respond to notifications appropriately."
  },
  // Settings/Profile
  'profile': {
    page: 'settings',
    label: 'Settings',
    prompts: [
      "Best practices for business settings",
      "How to set up my planner profile",
      "Contract default recommendations"
    ],
    systemHint: "User is managing their settings and profile. Help with business configuration and best practices."
  }
};

// Default prompts when no specific page context
const GENERAL_PROMPTS = [
  "What are typical wedding planning timelines?",
  "How do I choose between vendors?",
  "Tips for staying within budget"
];

const WEDDING_PROMPTS = [
  "What's my budget breakdown looking like?",
  "Suggest vendors for this wedding",
  "Cultural traditions I should know about"
];

// Get page context from pathname
function getPageContext(pathname: string | null): PageContext | null {
  if (!pathname) return null;

  // Check each context pattern
  for (const [pattern, context] of Object.entries(PAGE_CONTEXTS)) {
    if (pathname.includes(`/admin/${pattern}`)) {
      return context;
    }
  }
  return null;
}

export function AIChatWidget({ weddingId: propWeddingId, weddingName: propWeddingName }: AIChatWidgetProps) {
  const { token } = useAdmin();
  const pathname = usePathname();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creditsRemaining, setCreditsRemaining] = useState<number | null>(null);
  const [creditsWarning, setCreditsWarning] = useState<string | null>(null);

  // Wedding context state
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string | null>(propWeddingId || null);
  const [selectedWeddingName, setSelectedWeddingName] = useState<string | null>(propWeddingName || null);
  const [showWeddingSelector, setShowWeddingSelector] = useState(false);
  const [weddingsLoading, setWeddingsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Extract wedding ID from URL if on a wedding page
  useEffect(() => {
    if (propWeddingId) {
      setSelectedWeddingId(propWeddingId);
      setSelectedWeddingName(propWeddingName || null);
      return;
    }

    // Check URL pattern: /admin/weddings/[id] or /admin/weddings/[id]/...
    const match = pathname?.match(/\/admin\/weddings\/([^\/]+)/);
    if (match && match[1] && match[1] !== 'new') {
      const urlWeddingId = match[1];
      setSelectedWeddingId(urlWeddingId);
      // Find wedding name from loaded weddings
      const wedding = weddings.find(w => w.id === urlWeddingId);
      if (wedding) {
        setSelectedWeddingName(wedding.couple_names);
      }
    }
  }, [pathname, propWeddingId, propWeddingName, weddings]);

  const fetchWeddings = useCallback(async () => {
    setWeddingsLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/planner/metrics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setWeddings(data.weddings || []);

        // If we have a selected wedding ID from URL but no name, find it
        if (selectedWeddingId && !selectedWeddingName) {
          const wedding = data.weddings?.find((w: Wedding) => w.id === selectedWeddingId);
          if (wedding) {
            setSelectedWeddingName(wedding.couple_names);
          }
        }
      }
    } catch (err) {
      // Silently fail - not critical
    } finally {
      setWeddingsLoading(false);
    }
  }, [token, selectedWeddingId, selectedWeddingName]);

  // Fetch planner's weddings for selector
  useEffect(() => {
    if (token && isOpen && weddings.length === 0) {
      fetchWeddings();
    }
  }, [token, isOpen, weddings.length, fetchWeddings]);

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

  const fetchCredits = useCallback(async () => {
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
  }, [token]);

  // Fetch initial credits
  useEffect(() => {
    if (token && isOpen) {
      fetchCredits();
    }
  }, [token, isOpen, fetchCredits]);

  const sendMessage = useCallback(async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (!textToSend || isLoading || !token) return;

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: textToSend,
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

      // Get page context for enhanced AI responses
      const pageContext = getPageContext(pathname);

      const response = await fetch(`${baseUrl}/admin/ai/chat`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage.content,
          wedding_id: selectedWeddingId || null,
          conversation_history: conversationHistory,
          page_context: pageContext ? {
            page: pageContext.page,
            hint: pageContext.systemHint
          } : null
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

      if (response.status === 503) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData?.detail?.message || 'AI service is temporarily unavailable.';
        setError(message);
        return;
      }

      if (!response.ok) {
        // Extract detailed error message from response
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail;
        let errorMessage = 'Failed to get response';
        if (detail) {
          errorMessage = typeof detail === 'string' ? detail : (detail.message || JSON.stringify(detail));
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      const responseText = typeof data.response === 'string'
        ? data.response
        : typeof data.response?.text === 'string'
          ? data.response.text
          : '';

      if (!responseText.trim()) {
        throw new Error('AI returned an empty response');
      }

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'assistant',
        content: responseText,
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
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(formatAIChatError(errorMessage));
      toast.error('AI chat failed');
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, token, messages, selectedWeddingId, pathname]);

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

  const selectWedding = (wedding: Wedding | null) => {
    if (wedding) {
      setSelectedWeddingId(wedding.id);
      setSelectedWeddingName(wedding.couple_names);
    } else {
      setSelectedWeddingId(null);
      setSelectedWeddingName(null);
    }
    setShowWeddingSelector(false);
    // Clear chat when changing context
    clearChat();
  };

  const handleSuggestedPrompt = (prompt: string) => {
    sendMessage(prompt);
  };

  // Get page context
  const pageContext = getPageContext(pathname);

  // Get prompts based on context - page-specific > wedding-specific > general
  const suggestedPrompts = pageContext?.prompts || (selectedWeddingId ? WEDDING_PROMPTS : GENERAL_PROMPTS);

  // Floating button when closed
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        data-testid="ai-chat-launcher"
        className={`fixed z-40 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 ${getAIWidgetPositionClasses(pathname, false)}`}
        title="Chat with AI Assistant"
        aria-label="Chat with AI Assistant"
      >
        <Sparkles className="h-6 w-6" />
      </button>
    );
  }

  // Chat panel when open
  return (
    <div className={`fixed z-40 flex w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-gray-200 dark:bg-slate-800 dark:ring-slate-700 sm:w-[400px] ${getAIWidgetPositionClasses(pathname, true)} ${getAIWidgetPanelSizeClasses(pathname)}`}>
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-slate-700 to-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5" />
          <div>
            <h3 className="font-semibold">AI Wedding Assistant</h3>
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

      {/* Wedding Selector */}
      <div className="border-b border-gray-200 dark:border-slate-600 bg-gray-50 dark:bg-slate-700/50">
        <button
          onClick={() => setShowWeddingSelector(!showWeddingSelector)}
          className="w-full px-4 py-2 flex items-center justify-between text-sm hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-rose-500" />
            <span className="text-gray-700 dark:text-gray-200">
              {selectedWeddingName || 'Select a wedding for context'}
            </span>
          </div>
          {showWeddingSelector ? (
            <ChevronUp className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          )}
        </button>

        {showWeddingSelector && (
          <div className="px-2 pb-2 max-h-40 overflow-y-auto">
            {weddingsLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              </div>
            ) : weddings.length === 0 ? (
              <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-2">
                No weddings found
              </p>
            ) : (
              <>
                <button
                  onClick={() => selectWedding(null)}
                  className={`w-full text-left px-3 py-2 text-sm rounded-lg mb-1 transition-colors ${
                    !selectedWeddingId
                      ? 'bg-slate-200 dark:bg-slate-600 text-gray-900 dark:text-white'
                      : 'hover:bg-gray-100 dark:hover:bg-slate-600 text-gray-700 dark:text-gray-300'
                  }`}
                >
                  General (no wedding context)
                </button>
                {weddings.map(wedding => (
                  <button
                    key={wedding.id}
                    onClick={() => selectWedding(wedding)}
                    className={`w-full text-left px-3 py-2 text-sm rounded-lg mb-1 transition-colors ${
                      selectedWeddingId === wedding.id
                        ? 'bg-slate-200 dark:bg-slate-600 text-gray-900 dark:text-white'
                        : 'hover:bg-gray-100 dark:hover:bg-slate-600 text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    <div className="font-medium">{wedding.couple_names}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(wedding.date).toLocaleDateString()}
                      {wedding.cultural_style && ` • ${wedding.cultural_style}`}
                    </div>
                  </button>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {/* Credits warning */}
      {creditsWarning && (
        <div className="bg-amber-50 dark:bg-amber-900/30 px-4 py-2 text-xs text-amber-800 dark:text-amber-200 border-b border-amber-100 dark:border-amber-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <p>{creditsWarning}</p>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="scrollbar-visible-thin flex-1 space-y-4 overflow-y-auto bg-white p-4 dark:bg-slate-800">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 dark:text-gray-400">
            <Sparkles className="h-10 w-10 mb-3 text-slate-400 dark:text-slate-500" />
            <h4 className="font-medium text-gray-700 dark:text-gray-200">How can I help you today?</h4>
            <p className="text-xs mt-1 max-w-[280px] dark:text-gray-400">
              {selectedWeddingName
                ? `Ask about ${selectedWeddingName}'s budget, vendors, or traditions.`
                : 'Ask me anything about wedding planning.'
              }
            </p>

            {/* Suggested Prompts */}
            <div className="mt-4 w-full space-y-2">
              <p className="text-xs text-gray-400 dark:text-gray-500 uppercase tracking-wide">Try asking:</p>
              {suggestedPrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSuggestedPrompt(prompt)}
                  disabled={isLoading}
                  className="w-full text-left px-3 py-2 text-xs bg-gray-50 dark:bg-slate-700 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-600 transition-colors text-gray-700 dark:text-gray-300 disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
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
                  ? 'bg-slate-700 text-white rounded-br-md'
                  : 'bg-gray-100 dark:bg-slate-700 text-gray-800 dark:text-gray-100 rounded-bl-md'
              }`}
            >
              <div className="text-sm">
                {message.role === 'assistant' ? <AssistantMarkdown content={message.content} /> : message.content}
              </div>
              <div className={`flex items-center gap-2 mt-1 text-xs ${
                message.role === 'user' ? 'text-slate-300' : 'text-gray-400 dark:text-gray-500'
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
            <div className="bg-gray-100 dark:bg-slate-700 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex items-center gap-2 text-gray-500 dark:text-gray-300">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-center">
            <div className="flex max-w-[90%] items-start gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm leading-relaxed text-red-700 dark:bg-red-900/30 dark:text-red-300">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-slate-600 p-4 bg-white dark:bg-slate-800">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selectedWeddingName ? `Ask about ${selectedWeddingName}...` : "Ask about wedding planning..."}
            className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-4 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500 max-h-24 placeholder:text-gray-400 dark:placeholder:text-gray-500"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-700 dark:bg-slate-600 text-white transition-colors hover:bg-slate-800 dark:hover:bg-slate-500 disabled:bg-gray-300 dark:disabled:bg-slate-700 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 text-center">
          1 credit per message
        </p>
      </div>
    </div>
  );
}

export default AIChatWidget;
