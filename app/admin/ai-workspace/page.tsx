'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import UpgradeModal from '@/components/ui/UpgradeModal';
import PageHeader from '../components/PageHeader';
import { Card } from '../../components/ui/Card';
import {
  Send,
  Loader2,
  Sparkles,
  AlertCircle,
  Coins,
  Heart,
  ChevronDown,
  ChevronUp,
  BrainCircuit,
  Lightbulb,
  Activity,
  CheckCircle2,
  Zap
} from 'lucide-react';
import { formatAIChatError } from '@/components/ai/AIChatWidget';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  creditsUsed?: number;
  actions_executed?: any[];
}

interface Wedding {
  id: string;
  couple_names: string;
  date: string;
  cultural_style?: string;
  region?: string;
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
            className="font-medium underline decoration-indigo-400 underline-offset-2 text-indigo-600 dark:text-indigo-400"
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

export default function AIWorkspacePage() {
  const { token, userProfile } = useAdmin();
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creditsRemaining, setCreditsRemaining] = useState<number | null>(null);
  const [creditsWarning, setCreditsWarning] = useState<string | null>(null);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  // Agent Activity Log
  const [activities, setActivities] = useState<any[]>([]);

  // Wedding context state
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string | null>(null);
  const [selectedWeddingName, setSelectedWeddingName] = useState<string | null>(null);
  const [showWeddingSelector, setShowWeddingSelector] = useState(false);
  const [weddingsLoading, setWeddingsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
        if (data.weddings && data.weddings.length > 0 && !selectedWeddingId) {
            setSelectedWeddingId(data.weddings[0].id);
            setSelectedWeddingName(data.weddings[0].couple_names);
        }
      }
    } catch (err) {
      // Silently fail - not critical
    } finally {
      setWeddingsLoading(false);
    }
  }, [token, selectedWeddingId]);

  useEffect(() => {
    if (token) {
      fetchWeddings();
    }
  }, [token, fetchWeddings]);

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

  useEffect(() => {
    if (token) {
      fetchCredits();
    }
  }, [token, fetchCredits]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activities]);

  const isFreeTier = userProfile?.subscription_status === 'free' || userProfile?.subscription_status === 'none' || !userProfile?.subscription_status;

  const sendMessage = useCallback(async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (!textToSend || isLoading || !token) return;

    if (!selectedWeddingId) {
        toast.error("Please select a wedding first to use the Command Center.");
        return;
    }

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

    // Add thinking to activity
    const activityId = Date.now();
    setActivities(prev => [...prev, { id: activityId, status: 'thinking', action: 'Analyzing request...' }]);

    try {
      const baseUrl = getApiBaseUrl();
      
      const response = await fetch(`${baseUrl}/admin/ai/weddings/${selectedWeddingId}/command-center`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage.content,
          wedding_id: selectedWeddingId,
          execute_actions: !isFreeTier
        })
      });

      if (response.status === 402) {
        const data = await response.json();
        setError(`Insufficient credits. You need 1 credit but have ${data.detail?.available || 0}.`);
        setShowUpgradeModal(true);
        setActivities(prev => prev.filter(a => a.id !== activityId));
        return;
      }

      if (response.status === 429) {
        setError('Too many requests. Please wait a moment and try again.');
        setActivities(prev => prev.filter(a => a.id !== activityId));
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail;
        let errorMessage = 'Failed to get response';
        if (detail) {
          errorMessage = typeof detail === 'string' ? detail : (detail.message || JSON.stringify(detail));
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      const responseText = data.response || '';

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'assistant',
        content: responseText,
        timestamp: new Date(),
        creditsUsed: data.credits_used,
        actions_executed: data.actions_executed
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Update activities
      setActivities(prev => {
          const newActivities = prev.filter(a => a.id !== activityId); // Remove thinking
          if (data.actions_executed && data.actions_executed.length > 0) {
              data.actions_executed.forEach((act: any) => {
                  newActivities.push({
                      id: Date.now() + Math.random(),
                      status: 'complete',
                      action: `Executed: ${act.name}`,
                      preview: act.result?.preview_only
                  });
                  if (act.result?.preview_only) {
                      setShowUpgradeModal(true);
                  }
              });
          } else {
              newActivities.push({
                  id: Date.now() + Math.random(),
                  status: 'complete',
                  action: `Completed analysis without tools.`,
              });
          }
          return newActivities;
      });

      if (data.credits_remaining !== undefined) {
        setCreditsRemaining(data.credits_remaining);
      }
      if (data.warning) {
        setCreditsWarning(data.warning);
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get response';
      setError(formatAIChatError(errorMessage));
      toast.error('AI execution failed');
      setActivities(prev => prev.filter(a => a.id !== activityId));
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, token, selectedWeddingId, isFreeTier]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setActivities([]);
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
    clearChat();
  };

  const suggestedPrompts = [
    { title: "Audit Budget", text: "Analyze the budget for this wedding and suggest where we can cut costs." },
    { title: "RSVP Chaser", text: "Draft an RSVP reminder email to all guests who haven't responded yet." },
    { title: "Vendor Status", text: "Check which vendors we have hired and what categories we are missing." },
    { title: "Quick Tasks", text: "Add 'Finalize Caterer' and 'Send out invites' to my checklist." }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] space-y-6">
      <UpgradeModal isOpen={showUpgradeModal} onClose={() => setShowUpgradeModal(false)} />
      
      <PageHeader
        title="Command Center"
        description="Autonomous Agent Workspace"
      />
      
      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0 w-full">
        {/* Left sidebar: Context & Controls */}
        <div className="md:w-1/3 lg:w-1/4 flex flex-col gap-6">

          <Card className="p-5">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Heart className="h-4 w-4 text-rose-500" />
              Active Wedding
            </h3>
            
            <div className="relative">
              <button
                onClick={() => setShowWeddingSelector(!showWeddingSelector)}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <span className="font-medium text-slate-800 dark:text-slate-200 truncate">
                  {selectedWeddingName || 'No specific wedding'}
                </span>
                {showWeddingSelector ? (
                  <ChevronUp className="h-5 w-5 text-slate-500" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-slate-500" />
                )}
              </button>

              {showWeddingSelector && (
                <div className="absolute z-10 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl max-h-60 overflow-y-auto">
                  {weddingsLoading ? (
                    <div className="p-4 flex justify-center">
                      <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                    </div>
                  ) : (
                    <div className="p-2 space-y-1">
                      {weddings.map(wedding => (
                        <button
                          key={wedding.id}
                          onClick={() => selectWedding(wedding)}
                          className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${selectedWeddingId === wedding.id ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium' : 'hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300'}`}
                        >
                          <div className="truncate">{wedding.couple_names}</div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            {new Date(wedding.date).toLocaleDateString()}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Activity Log Panel */}
          <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary-500" />
                Agent Activity
              </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {activities.length === 0 ? (
                <div className="text-center text-sm text-slate-400 py-8">
                  Waiting for instructions...
                </div>
              ) : (
                activities.map(activity => (
                  <div key={activity.id} className="flex items-start gap-3">
                    {activity.status === 'thinking' ? (
                      <Loader2 className="h-4 w-4 text-primary-500 animate-spin mt-0.5" />
                    ) : activity.preview ? (
                      <Zap className="h-4 w-4 text-amber-500 mt-0.5" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5" />
                    )}
                    <div>
                      <p className={`text-sm ${activity.status === 'thinking' ? 'text-primary-600 font-medium' : 'text-slate-700 dark:text-slate-300'}`}>
                        {activity.action}
                      </p>
                      {activity.preview && (
                        <span className="inline-block mt-1 px-2 py-0.5 bg-amber-100 text-amber-800 text-[10px] uppercase font-bold rounded">
                          Preview Only
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>

        {/* Center: Chat Area */}
        <Card className="md:w-2/3 lg:w-3/4 flex flex-col min-h-0 overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
            <h2 className="font-semibold text-slate-800 dark:text-slate-200">
              Conversation
            </h2>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5 text-sm font-medium text-slate-500 bg-white dark:bg-slate-800 px-3 py-1 rounded-full shadow-sm border border-slate-100 dark:border-slate-700">
                <Coins className="h-4 w-4 text-amber-500" />
                {creditsRemaining !== null ? creditsRemaining : <Loader2 className="h-3 w-3 animate-spin" />} left
              </span>
              <button
                onClick={clearChat}
                className="text-sm font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
              >
                Clear
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center max-w-2xl mx-auto text-center">
                <div className="bg-primary-100 dark:bg-primary-900/30 p-6 rounded-full mb-6 shadow-inner">
                  <Sparkles className="h-12 w-12 text-primary-600 dark:text-primary-400" />
                </div>
                <h3 className="text-2xl font-bold text-slate-800 dark:text-slate-200 mb-3">
                  I can run your entire wedding.
                </h3>
                <p className="text-slate-500 dark:text-slate-400 mb-8 max-w-lg">
                  Tell me what you need done. I can read your budget, contact your vendors, check on guests, and build your timeline automatically.
                </p>

                <div className="w-full grid grid-cols-2 gap-4">
                  {suggestedPrompts.map((prompt, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(prompt.text)}
                      className="text-left p-5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-primary-300 dark:hover:border-primary-700 transition-all shadow-sm group"
                    >
                      <h4 className="font-semibold text-slate-800 dark:text-slate-200 mb-1 flex items-center gap-2">
                        <Zap className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-transform" />
                        {prompt.title}
                      </h4>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{prompt.text}</p>
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
                {message.role === 'assistant' && (
                  <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center mr-3 mt-1 flex-shrink-0">
                    <Sparkles className="h-4 w-4 text-white" />
                  </div>
                )}
                
                <div
                  className={`max-w-[85%] rounded-2xl px-5 py-3 ${
                    message.role === 'user'
                      ? 'bg-primary-600 text-white rounded-tr-sm'
                      : 'bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-tl-sm shadow-sm'
                  }`}
                >
                  <div className="text-sm prose prose-sm prose-slate dark:prose-invert">
                    {message.role === 'assistant' ? <AssistantMarkdown content={message.content} /> : message.content}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center mr-3 mt-1 flex-shrink-0">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm">
                  <div className="flex items-center gap-3 text-slate-500 dark:text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm font-medium tracking-wide">Executing Actions...</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="flex justify-center mt-4">
                <div className="flex max-w-[90%] items-start gap-2 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 px-5 py-3 text-sm leading-relaxed text-red-700 dark:text-red-400 shadow-sm">
                  <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 sm:p-6 bg-slate-50 dark:bg-slate-900/50 border-t border-slate-200 dark:border-slate-700">
            <div className="relative flex items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedWeddingName ? `Instruct the agent to manage ${selectedWeddingName}...` : "Please select a wedding first..."}
                className="w-full resize-none rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 pl-5 pr-14 py-4 text-base focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 min-h-[60px] max-h-40 placeholder:text-slate-400 shadow-sm disabled:opacity-50"
                rows={1}
                disabled={isLoading || !selectedWeddingId}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isLoading || !selectedWeddingId}
                className="absolute right-3 bottom-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary-600 text-white transition-all hover:bg-primary-700 hover:shadow-md disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:cursor-not-allowed disabled:hover:shadow-none"
              >
                {isLoading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5 translate-x-[-1px] translate-y-[1px]" />
                )}
              </button>
            </div>
            <div className="mt-3 flex justify-between items-center text-xs text-slate-500 dark:text-slate-400 px-1">
              <span>Press <kbd className="font-sans font-medium px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-md">Enter</kbd> to execute</span>
              <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" /> Autonomous Agent Engine</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
