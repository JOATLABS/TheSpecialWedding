'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { useSSE } from '@/hooks/useSSE';
import { formatDate } from '@/utils/dateFormat';
import {
  Mail,
  Reply,
  CheckCheck,
  Inbox,
  Paperclip,
  ArrowLeft,
  Send,
  Filter,
  RefreshCw,
  MailOpen,
  GripVertical,
  MessageCircle,
  Heart,
  ChevronDown
} from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import InboxListItem from '@/components/ui/InboxListItem';
import MessageBubble from '@/components/ui/MessageBubble';
import ChatInput from '@/components/ui/ChatInput';
import { getApiBaseUrl } from '@/utils/env';

// ==================== TYPES ====================

interface InboundEmail {
  id: string;
  from_address: string;
  from_name?: string;
  subject: string;
  preview: string;
  thread_id?: string;
  guest_name?: string;
  wedding_slug?: string;
  wedding_id?: string;
  is_read: boolean;
  planner_response_sent: boolean;
  created_at: string;
  has_attachments: boolean;
  status: string;
  html_body?: string;
  text_body?: string;
  attachments?: any[];
  direction?: string;
}

interface InboxResponse {
  emails: InboundEmail[];
  total: number;
  page: number;
  pages: number;
  unread_count: number;
}

interface CoupleConversationSummary {
  id: string;
  email: string;
  partner1_name?: string;
  partner2_name?: string;
  wedding_id: string;
  last_login?: string;
  created_at?: string;
  last_message_at?: string;
  last_message_preview?: string;
  last_sender_role?: string;
  unread_count: number;
}

interface CoupleMessage {
  id: string;
  sender_role: string;
  sender_name: string;
  content: string;
  read_by_couple: boolean;
  created_at: string;
}

interface Wedding {
  _id: string;
  partner1_first_name?: string;
  partner1_last_name?: string;
  partner2_first_name?: string;
  partner2_last_name?: string;
  wedding_date?: string;
  slug?: string;
}

// A single item in the unified inbox list
interface InboxItem {
  id: string;
  type: 'email' | 'couple';
  name: string;
  preview: string;
  is_read: boolean;
  created_at: string;
  wedding_id?: string;
  wedding_label?: string;
  // type-specific data
  email?: InboundEmail;
  couple?: CoupleConversationSummary;
  unread_count?: number;
}

// ==================== MAIN PAGE ====================

export default function CommunicationsInboxView() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const baseUrl = getApiBaseUrl();
  const requestedWeddingId = searchParams.get('wedding_id') || 'all';
  const requestedConversation = searchParams.get('conversation');
  const canAccessCoupleMessages = Boolean(
    userProfile?.is_root_admin ||
    userProfile?.is_wedding_planner ||
    userProfile?.team_permissions?.manage_contracts
  );

  // ---- Weddings for filter ----
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string>(() => requestedWeddingId);
  const [showWeddingDropdown, setShowWeddingDropdown] = useState(false);
  const weddingDropdownRef = useRef<HTMLDivElement>(null);

  // ---- Email state ----
  const [emails, setEmails] = useState<InboundEmail[]>([]);
  const [emailLoading, setEmailLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterUnread, setFilterUnread] = useState(false);

  // ---- Couple conversations state ----
  const [coupleConversations, setCoupleConversations] = useState<CoupleConversationSummary[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);

  // ---- Selected conversation ----
  const [selectedItem, setSelectedItem] = useState<InboxItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  // Email detail
  const [selectedEmailDetail, setSelectedEmailDetail] = useState<InboundEmail | null>(null);

  // Couple messages detail
  const [coupleMessages, setCoupleMessages] = useState<CoupleMessage[]>([]);

  // Reply / compose
  const [replyText, setReplyText] = useState('');
  const [showReply, setShowReply] = useState(false);
  const [sending, setSending] = useState(false);

  // Draggable panel resize
  const [listWidthPercent, setListWidthPercent] = useState(40);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Close wedding dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (weddingDropdownRef.current && !weddingDropdownRef.current.contains(e.target as Node)) {
        setShowWeddingDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    setSelectedWeddingId((current) => (current === requestedWeddingId ? current : requestedWeddingId));
  }, [requestedWeddingId]);

  useEffect(() => {
    if (!weddings.length) return;
    if (selectedWeddingId === 'all') return;
    if (!weddings.some((wedding) => wedding._id === selectedWeddingId)) {
      setSelectedWeddingId('all');
    }
  }, [selectedWeddingId, weddings]);

  useEffect(() => {
    if (!pathname) return;
    if (selectedWeddingId === requestedWeddingId) return;

    const params = new URLSearchParams(searchParams.toString());
    if (selectedWeddingId === 'all') {
      params.delete('wedding_id');
    } else {
      params.set('wedding_id', selectedWeddingId);
    }

    const nextQuery = params.toString();
    const nextUrl = nextQuery ? `${pathname}?${nextQuery}` : pathname;
    router.replace(nextUrl, { scroll: false });
  }, [pathname, requestedWeddingId, router, searchParams, selectedWeddingId]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const percent = (x / rect.width) * 100;
      setListWidthPercent(Math.min(70, Math.max(20, percent)));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, []);

  // ==================== DATA FETCHING ====================

  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch(`${baseUrl}/admin/weddings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        // Handle both array and object response
        const weddingList = Array.isArray(data) ? data : (data.weddings || []);
        setWeddings(weddingList);
      }
    } catch (error) {
      console.error('Failed to fetch weddings:', error);
    }
  }, [token, baseUrl]);

  const fetchEmails = useCallback(async () => {
    if (!token) return;
    try {
      setEmailLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '50',
        unread_only: filterUnread.toString()
      });

      const response = await fetch(`${baseUrl}/admin/inbound-emails/inbox?${params}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.ok) {
        const data: InboxResponse = await response.json();
        setEmails(data.emails);
        setTotal(data.total);
        setPages(data.pages);
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch inbox:', error);
    } finally {
      setEmailLoading(false);
    }
  }, [token, baseUrl, page, filterUnread]);

  const markCoupleConversationRead = useCallback(async (weddingId: string) => {
    if (!token || !canAccessCoupleMessages) return;

    try {
      await fetch(`${baseUrl}/couple-portal/messages/read`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ wedding_id: weddingId }),
      });
      setCoupleConversations((prev) =>
        prev.map((conversation) =>
          conversation.wedding_id === weddingId
            ? { ...conversation, unread_count: 0 }
            : conversation
        )
      );
    } catch (error) {
      console.error('Failed to mark couple conversation as read:', error);
    }
  }, [baseUrl, canAccessCoupleMessages, token]);

  const fetchCoupleConversations = useCallback(async () => {
    if (!token) return;
    if (!canAccessCoupleMessages) {
      setCoupleConversations([]);
      setConversationsLoading(false);
      return;
    }

    try {
      setConversationsLoading(true);
      const params = new URLSearchParams();
      if (selectedWeddingId !== 'all') {
        params.set('wedding_id', selectedWeddingId);
      }

      const response = await fetch(`${baseUrl}/couple-portal/conversations?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setCoupleConversations(data.conversations || []);
      }
    } catch (error) {
      console.error('Failed to fetch couple conversations:', error);
    } finally {
      setConversationsLoading(false);
    }
  }, [token, baseUrl, canAccessCoupleMessages, selectedWeddingId]);

  useEffect(() => { fetchWeddings(); }, [fetchWeddings]);
  useEffect(() => { fetchEmails(); }, [fetchEmails]);
  useEffect(() => { fetchCoupleConversations(); }, [fetchCoupleConversations]);

  const fetchEmailDetail = useCallback(async (emailId: string) => {
    if (!token) return;
    try {
      setDetailLoading(true);
      const response = await fetch(`${baseUrl}/admin/inbound-emails/${emailId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedEmailDetail(data);
      }
    } catch (error) {
      console.error('Failed to fetch email detail:', error);
    } finally {
      setDetailLoading(false);
    }
  }, [baseUrl, token]);

  const fetchCoupleMessages = useCallback(async (weddingId: string, options?: { markRead?: boolean }) => {
    if (!token) return;
    try {
      setDetailLoading(true);
      const response = await fetch(
        `${baseUrl}/couple-portal/messages?wedding_id=${weddingId}&limit=100`,
        { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
      );
      if (response.ok) {
        const data = await response.json();
        setCoupleMessages(data.messages || []);
        if (options?.markRead) {
          await markCoupleConversationRead(weddingId);
        }
      }
    } catch (error) {
      console.error('Failed to fetch couple messages:', error);
    } finally {
      setDetailLoading(false);
    }
  }, [baseUrl, markCoupleConversationRead, token]);

  // Auto-scroll to bottom for couple chat
  useEffect(() => {
    if (selectedItem?.type === 'couple' && coupleMessages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [coupleMessages, selectedItem]);

  // ==================== BUILD UNIFIED LIST ====================

  const getWeddingLabel = useCallback((weddingId?: string): string => {
    if (!weddingId) return '';
    const w = weddings.find(w => w._id === weddingId);
    if (!w) return '';
    const p1 = [w.partner1_first_name, w.partner1_last_name].filter(Boolean).join(' ');
    const p2 = [w.partner2_first_name, w.partner2_last_name].filter(Boolean).join(' ');
    if (p1 && p2) return `${p1} & ${p2}`;
    return p1 || p2 || w.slug || weddingId;
  }, [weddings]);

  const buildUnifiedList = useCallback((): InboxItem[] => {
    const items: InboxItem[] = [];

    for (const email of emails) {
      items.push({
        id: `email_${email.id}`,
        type: 'email',
        name: email.guest_name || email.from_name || email.from_address,
        preview: email.subject || email.preview,
        is_read: email.is_read,
        created_at: email.created_at,
        wedding_id: email.wedding_id,
        wedding_label: getWeddingLabel(email.wedding_id),
        email,
      });
    }

    for (const conversation of coupleConversations) {
      const coupleName = [conversation.partner1_name, conversation.partner2_name]
        .filter(Boolean)
        .join(' & ') || conversation.email;
      const unread = conversation.unread_count || 0;
      const preview = conversation.last_message_preview
        ? `${conversation.last_sender_role === 'planner' ? 'You: ' : ''}${conversation.last_message_preview}`
        : 'Couple conversation';

      items.push({
        id: `couple_${conversation.id}`,
        type: 'couple',
        name: coupleName,
        preview,
        is_read: unread === 0,
        created_at: conversation.last_message_at || conversation.last_login || conversation.created_at || '',
        wedding_id: conversation.wedding_id,
        wedding_label: getWeddingLabel(conversation.wedding_id),
        couple: conversation,
        unread_count: unread,
      });
    }

    // Sort by most recent
    items.sort((a, b) => {
      // Unread first, then by date
      if (!a.is_read && b.is_read) return -1;
      if (a.is_read && !b.is_read) return 1;
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return dateB - dateA;
    });

    return items;
  }, [coupleConversations, emails, getWeddingLabel]);

  const allItems = buildUnifiedList();

  // Apply wedding filter
  const inboxItems = selectedWeddingId === 'all'
    ? allItems
    : allItems.filter(item => item.wedding_id === selectedWeddingId);

  // Apply unread filter
  const filteredItems = filterUnread
    ? inboxItems.filter(item => !item.is_read)
    : inboxItems;

  const loading = emailLoading || conversationsLoading;
  const totalUnread = unreadCount + coupleConversations.reduce((totalUnreadCount, conversation) => totalUnreadCount + (conversation.unread_count || 0), 0);

  const selectedWeddingLabel = selectedWeddingId === 'all'
    ? 'All Weddings'
    : getWeddingLabel(selectedWeddingId) || selectedWeddingId;

  useSSE({
    resources: ['couple_message'],
    weddingId: selectedWeddingId === 'all' ? null : selectedWeddingId,
    enabled: canAccessCoupleMessages,
    onDataChange: (event) => {
      void fetchCoupleConversations();

      if (selectedItem?.type !== 'couple' || !selectedItem.couple) {
        return;
      }

      if (event.resource === '__reconnected__' || event.wedding_id === selectedItem.couple.wedding_id) {
        void fetchCoupleMessages(selectedItem.couple.wedding_id, { markRead: true });
      }
    },
  });

  // ==================== ACTIONS ====================

  const handleSelectItem = useCallback(async (item: InboxItem) => {
    setSelectedItem(item);
    setShowReply(false);
    setReplyText('');
    setMobileShowDetail(true);
    setSelectedEmailDetail(null);
    setCoupleMessages([]);

    if (item.type === 'email' && item.email) {
      await fetchEmailDetail(item.email.id);
      if (!item.email.is_read) {
        setEmails(prev =>
          prev.map(e => e.id === item.email!.id ? { ...e, is_read: true } : e)
        );
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } else if (item.type === 'couple' && item.couple) {
      await fetchCoupleMessages(item.couple.wedding_id, { markRead: true });
    }
  }, [fetchCoupleMessages, fetchEmailDetail]);

  const handleMarkAllRead = async () => {
    if (!token) return;
    try {
      await fetch(`${baseUrl}/admin/inbound-emails/read-all`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` }
      });
      setEmails(prev => prev.map(e => ({ ...e, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  const handleSendReply = async () => {
    if (!token || !selectedItem || !replyText.trim()) return;

    if (selectedItem.type === 'email' && selectedItem.email) {
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/admin/inbound-emails/${selectedItem.email.id}/reply`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            html_content: `<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">${replyText.replace(/\n/g, '<br>')}</div>`,
            text_content: replyText
          })
        });

        if (response.ok) {
          setReplyText('');
          setShowReply(false);
          setEmails(prev =>
            prev.map(e =>
              e.id === selectedItem.email!.id ? { ...e, planner_response_sent: true } : e
            )
          );
        } else {
          const err = await response.json();
          alert(`Failed to send reply: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send reply:', error);
        alert('Failed to send reply. Please try again.');
      } finally {
        setSending(false);
      }
    } else if (selectedItem.type === 'couple' && selectedItem.couple) {
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/couple-portal/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            wedding_id: selectedItem.couple.wedding_id,
            content: replyText
          })
        });

        if (response.ok) {
          setReplyText('');
          await fetchCoupleMessages(selectedItem.couple.wedding_id);
        } else {
          const err = await response.json();
          alert(`Failed to send message: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send message:', error);
        alert('Failed to send message. Please try again.');
      } finally {
        setSending(false);
      }
    }
  };

  const handleRefresh = () => {
    fetchEmails();
    fetchCoupleConversations();
    if (selectedItem?.type === 'couple' && selectedItem.couple) {
      void fetchCoupleMessages(selectedItem.couple.wedding_id, { markRead: true });
    } else if (selectedItem?.type === 'email' && selectedItem.email) {
      void fetchEmailDetail(selectedItem.email.id);
    }
  };

  useEffect(() => {
    if (loading) return;
    if (requestedConversation !== 'couple' || requestedWeddingId === 'all') return;
    const targetConversation = filteredItems.find(
      (item) => item.type === 'couple' && item.wedding_id === requestedWeddingId
    );
    if (!targetConversation) return;
    if (selectedItem?.id === targetConversation.id) return;
    void handleSelectItem(targetConversation);
  }, [filteredItems, handleSelectItem, loading, requestedConversation, requestedWeddingId, selectedItem?.id]);

  // ==================== DETAIL RENDERERS ====================

  const renderEmailDetail = () => {
    if (!selectedEmailDetail) return null;

    return (
      <>
        <div className="p-4 border-b border-gray-100 dark:border-slate-800">
          <button
            onClick={() => { setMobileShowDetail(false); setSelectedItem(null); setSelectedEmailDetail(null); }}
            className="lg:hidden flex items-center gap-1 text-sm text-gray-500 mb-3"
          >
            <ArrowLeft size={16} />
            Back to inbox
          </button>

          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
            {selectedEmailDetail.subject}
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                From: <span className="font-medium">{selectedEmailDetail.from_name || selectedEmailDetail.from_address}</span>
                {selectedEmailDetail.from_name && (
                  <span className="text-gray-400 ml-1">&lt;{selectedEmailDetail.from_address}&gt;</span>
                )}
              </p>
              {selectedEmailDetail.guest_name && selectedEmailDetail.guest_name !== selectedEmailDetail.from_name && (
                <p className="text-xs text-gray-400 mt-0.5">
                  Guest: {selectedEmailDetail.guest_name}
                </p>
              )}
            </div>
            <span className="text-xs text-gray-400">
              {formatDate(selectedEmailDetail.created_at)}
            </span>
          </div>

          {selectedEmailDetail.planner_response_sent && (
            <div className="mt-2 flex items-center gap-1 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-1 rounded-md w-fit">
              <CheckCheck size={12} />
              You replied to this email
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {detailLoading ? (
            <div className="text-center text-gray-400 py-8">
              <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
              Loading email content...
            </div>
          ) : selectedEmailDetail.status === 'received' ? (
            <div className="text-center text-gray-400 py-8">
              <Mail className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>Email content is being fetched...</p>
              <p className="text-xs mt-1">This usually takes a few seconds. Try refreshing.</p>
              <button
                onClick={() => selectedItem?.email && fetchEmailDetail(selectedItem.email.id)}
                className="mt-3 text-sm text-rose-500 hover:text-rose-600"
              >
                Refresh
              </button>
            </div>
          ) : selectedEmailDetail.html_body ? (
            <div
              className="prose prose-sm max-w-none dark:prose-invert"
              dangerouslySetInnerHTML={{ __html: selectedEmailDetail.html_body }}
            />
          ) : selectedEmailDetail.text_body ? (
            <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-sans leading-relaxed">
              {selectedEmailDetail.text_body}
            </pre>
          ) : (
            <div className="text-center text-gray-400 py-8">
              <MailOpen className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>No email content available</p>
            </div>
          )}

          {selectedEmailDetail.attachments && selectedEmailDetail.attachments.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 dark:border-slate-800">
              <p className="text-xs font-medium text-gray-500 mb-2">Attachments</p>
              <div className="flex flex-wrap gap-2">
                {selectedEmailDetail.attachments.map((att: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-50 dark:bg-slate-800 rounded-md text-xs text-gray-600 dark:text-gray-400"
                  >
                    <Paperclip size={12} />
                    {att.filename || 'Attachment'}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {showReply ? (
          <div className="p-4 border-t border-gray-100 dark:border-slate-800 bg-gray-50 dark:bg-slate-800/50">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Type your reply..."
              className="w-full p-3 border border-gray-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent resize-none"
              rows={5}
              autoFocus
            />
            <div className="flex items-center justify-between mt-2">
              <button
                onClick={() => { setShowReply(false); setReplyText(''); }}
                className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                Cancel
              </button>
              <button
                onClick={handleSendReply}
                disabled={sending || !replyText.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-rose-500 text-white rounded-lg text-sm font-medium hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                <Send size={14} />
                {sending ? 'Sending...' : 'Send Reply'}
              </button>
            </div>
          </div>
        ) : (
          <div className="p-3 border-t border-gray-100 dark:border-slate-800">
            <button
              onClick={() => setShowReply(true)}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-rose-500 text-white rounded-lg text-sm font-medium hover:bg-rose-600 transition"
            >
              <Reply size={16} />
              Reply
            </button>
          </div>
        )}
      </>
    );
  };

  const renderCoupleChat = () => {
    const couple = selectedItem?.couple;
    if (!couple) return null;

    const coupleName = [couple.partner1_name, couple.partner2_name]
      .filter(Boolean)
      .join(' & ') || couple.email;

    return (
      <>
        <div className="p-4 border-b border-gray-100 dark:border-slate-800">
          <button
            onClick={() => { setMobileShowDetail(false); setSelectedItem(null); setCoupleMessages([]); }}
            className="lg:hidden flex items-center gap-1 text-sm text-gray-500 mb-3"
          >
            <ArrowLeft size={16} />
            Back to inbox
          </button>

          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
              <Heart size={16} className="text-rose-500" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {coupleName}
              </h2>
              <p className="text-xs text-gray-400">{couple.email}</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {detailLoading ? (
            <div className="text-center text-gray-400 py-8">
              <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
              Loading messages...
            </div>
          ) : coupleMessages.length === 0 ? (
            <div className="text-center text-gray-400 py-8">
              <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="font-medium">No messages yet</p>
              <p className="text-sm mt-1">Start the conversation with {coupleName}</p>
            </div>
          ) : (
            coupleMessages.map((msg) => (
              <MessageBubble
                key={msg.id}
                content={msg.content}
                senderName={msg.sender_role !== 'planner' ? msg.sender_name : undefined}
                isSelf={msg.sender_role === 'planner'}
                timestamp={msg.created_at ? formatDate(msg.created_at) : undefined}
                accentColor="rose"
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput
          value={replyText}
          onChange={setReplyText}
          onSend={handleSendReply}
          sending={sending}
          placeholder={`Message ${coupleName}...`}
          accentColor="rose"
        />
      </>
    );
  };

  // ==================== RENDER ====================

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox"
        description="All messages — guest replies and couple conversations"
      />

      <div>
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {filteredItems.length} conversation{filteredItems.length !== 1 ? 's' : ''}
              {totalUnread > 0 && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400">
                  {totalUnread} unread
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Wedding filter dropdown */}
            <div ref={weddingDropdownRef} className="relative">
              <button
                onClick={() => setShowWeddingDropdown(!showWeddingDropdown)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400 transition border border-gray-200 dark:border-slate-700"
              >
                <Heart size={14} />
                <span className="max-w-[150px] truncate">{selectedWeddingLabel}</span>
                <ChevronDown size={14} />
              </button>

              {showWeddingDropdown && (
                <div className="absolute right-0 top-full mt-1 w-64 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-gray-200 dark:border-slate-700 z-50 max-h-64 overflow-y-auto">
                  <button
                    onClick={() => { setSelectedWeddingId('all'); setShowWeddingDropdown(false); }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition ${
                      selectedWeddingId === 'all' ? 'bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-medium' : 'text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    All Weddings
                  </button>
                  {weddings.map((w) => {
                    const p1 = [w.partner1_first_name, w.partner1_last_name].filter(Boolean).join(' ');
                    const p2 = [w.partner2_first_name, w.partner2_last_name].filter(Boolean).join(' ');
                    const label = (p1 && p2) ? `${p1} & ${p2}` : p1 || p2 || w.slug || w._id;
                    return (
                      <button
                        key={w._id}
                        onClick={() => { setSelectedWeddingId(w._id); setShowWeddingDropdown(false); }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition ${
                          selectedWeddingId === w._id ? 'bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-medium' : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <button
              onClick={() => setFilterUnread(!filterUnread)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
                filterUnread
                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400'
                  : 'bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400'
              }`}
            >
              <Filter size={14} />
              {filterUnread ? 'Unread' : 'All'}
            </button>

            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400 transition"
              >
                <CheckCheck size={14} />
                Mark emails read
              </button>
            )}

            <button
              onClick={handleRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400 transition"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Main content area */}
        <div ref={containerRef} className="flex min-h-[600px] gap-0">

          {/* List Panel */}
          <div
            className={`bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 overflow-hidden flex-shrink-0 ${mobileShowDetail ? 'hidden lg:block' : ''}`}
            style={{ width: `${listWidthPercent}%` }}
          >
            <div className="divide-y divide-gray-100 dark:divide-slate-800 max-h-[calc(100vh-250px)] overflow-y-auto">
              {loading ? (
                <div className="p-8 text-center text-gray-400">
                  <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  <p>Loading messages...</p>
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="p-12 text-center text-gray-400">
                  <Inbox className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p className="font-medium mb-1">No messages</p>
                  <p className="text-sm">
                    {filterUnread
                      ? 'No unread messages. Try showing all.'
                      : selectedWeddingId !== 'all'
                        ? 'No messages for this wedding yet.'
                        : 'Guest replies and couple messages will appear here.'}
                  </p>
                </div>
              ) : (
                filteredItems.map((item) => (
                  <InboxListItem
                    key={item.id}
                    id={item.id}
                    type={item.type}
                    name={item.name}
                    preview={item.preview}
                    isRead={item.is_read}
                    isSelected={selectedItem?.id === item.id}
                    timestamp={item.created_at ? formatDate(item.created_at) : ''}
                    unreadCount={item.type === 'couple' ? item.unread_count : undefined}
                    weddingLabel={item.wedding_label}
                    hasAttachments={item.type === 'email' ? item.email?.has_attachments : undefined}
                    hasReplied={item.type === 'email' ? item.email?.planner_response_sent : undefined}
                    accentColor="rose"
                    onClick={() => handleSelectItem(item)}
                  />
                ))
              )}
            </div>

            {pages > 1 && (
              <div className="flex items-center justify-between p-3 border-t border-gray-100 dark:border-slate-800">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30"
                >
                  Previous
                </button>
                <span className="text-xs text-gray-400">
                  Page {page} of {pages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(pages, p + 1))}
                  disabled={page >= pages}
                  className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </div>

          {/* Drag Handle */}
          <div
            onMouseDown={handleMouseDown}
            className="hidden lg:flex items-center justify-center w-3 cursor-col-resize group flex-shrink-0 hover:bg-slate-200/50 dark:hover:bg-slate-700/50 rounded transition-colors mx-0.5"
            title="Drag to resize panels"
          >
            <GripVertical className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 dark:group-hover:text-slate-400 transition-colors" />
          </div>

          {/* Detail Panel */}
          <div className={`flex-1 min-w-0 ${!mobileShowDetail ? 'hidden lg:block' : ''}`}>
            {selectedItem ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex flex-col h-[calc(100vh-250px)]">
                {selectedItem.type === 'email' && selectedEmailDetail
                  ? renderEmailDetail()
                  : selectedItem.type === 'couple'
                    ? renderCoupleChat()
                    : (
                      <div className="flex-1 flex items-center justify-center text-gray-400">
                        <div className="text-center">
                          <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
                          <p>Loading...</p>
                        </div>
                      </div>
                    )
                }
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex items-center justify-center h-[calc(100vh-250px)]">
                <div className="text-center text-gray-400">
                  <Inbox className="w-14 h-14 mx-auto mb-4 opacity-30" />
                  <p className="font-medium text-gray-500 dark:text-gray-400">Select a conversation</p>
                  <p className="text-sm mt-1">Choose a message from the list</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
