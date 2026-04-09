'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { useSSE } from '@/hooks/useSSE';
import {
  canAccessGuestCommunications,
  canAccessSupportInbox,
  canMessageCouples,
} from '@/admin/utils/teamAccess';
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
  MessageSquare,
  Heart,
  ChevronDown,
  Smartphone,
  AlertCircle,
} from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import InboxListItem from '@/components/ui/InboxListItem';
import MessageBubble from '@/components/ui/MessageBubble';
import ChatInput from '@/components/ui/ChatInput';
import { getApiBaseUrl } from '@/utils/env';

type InboxConversationType =
  | 'email'
  | 'couple'
  | 'sms_support'
  | 'support_ticket';
type DeepLinkConversation = 'couple' | 'sms_support' | 'support_ticket';

const SUPPORTED_QUERY_CONVERSATIONS = new Set<DeepLinkConversation>([
  'couple',
  'sms_support',
  'support_ticket',
]);

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
  attachments?: Array<{ filename?: string }>;
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

interface SMSResponse {
  message: string;
  sent_by?: string;
  sent_by_name?: string;
  sent_at?: string;
}

interface SMSSupportTicket {
  _id: string;
  phone: string;
  message: string;
  guest_id?: string | null;
  guest_name?: string | null;
  wedding_id?: string | null;
  wedding_name?: string;
  assigned_to?: string | null;
  planner_name?: string;
  status: 'new' | 'in_progress' | 'resolved' | 'closed';
  created_at: string;
  updated_at?: string;
  read_at?: string;
  is_read?: boolean;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  type?: string;
  source?: string;
  responses?: SMSResponse[];
}

interface SMSTicketsResponse {
  tickets: SMSSupportTicket[];
  total: number;
  page: number;
  pages: number;
  limit: number;
}

interface SupportComment {
  id: string;
  user_id: string;
  message: string;
  created_at: string;
  is_internal?: boolean;
  user_info?: {
    first_name?: string;
    last_name?: string;
    role?: string;
  };
}

interface PlannerSupportTicket {
  _id: string;
  ticket_number?: string;
  subject: string;
  description?: string;
  message?: string;
  category?: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  created_at: string;
  updated_at?: string;
  wedding_id?: string | null;
  created_by?: string;
  creator_info?: {
    first_name?: string;
    last_name?: string;
    company_name?: string;
    email?: string;
  };
  comments?: SupportComment[];
  source?: string;
}

interface SupportTicketsResponse {
  tickets: PlannerSupportTicket[];
  total: number;
  page: number;
  pages: number;
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

interface InboxItem {
  id: string;
  type: InboxConversationType;
  name: string;
  preview: string;
  is_read: boolean;
  created_at: string;
  wedding_id?: string;
  wedding_label?: string;
  email?: InboundEmail;
  couple?: CoupleConversationSummary;
  smsSupport?: SMSSupportTicket;
  supportTicket?: PlannerSupportTicket;
  unread_count?: number;
}

function getLatestSmsActivity(ticket: SMSSupportTicket): string {
  const responses = ticket.responses || [];
  const latestResponse = responses[responses.length - 1];
  return latestResponse?.sent_at || ticket.updated_at || ticket.created_at;
}

function getSmsDisplayName(ticket: SMSSupportTicket): string {
  return ticket.guest_name?.trim() || ticket.phone || ticket.wedding_name || 'Guest SMS';
}

function getSmsPreview(ticket: SMSSupportTicket): string {
  const responses = ticket.responses || [];
  const latestResponse = responses[responses.length - 1];
  if (latestResponse?.message) {
    return `You: ${latestResponse.message}`;
  }
  return `${getSmsDisplayName(ticket)}: ${ticket.message}`;
}

function getPublicSupportComments(ticket: PlannerSupportTicket): SupportComment[] {
  return (ticket.comments || []).filter((comment) => !comment.is_internal);
}

function getSupportTicketPreview(ticket: PlannerSupportTicket): string {
  const publicComments = getPublicSupportComments(ticket);
  const latestComment = publicComments[publicComments.length - 1];
  if (latestComment?.message) {
    return latestComment.message;
  }
  return ticket.description || ticket.message || ticket.subject;
}

function getSupportTicketActivity(ticket: PlannerSupportTicket): string {
  const publicComments = getPublicSupportComments(ticket);
  const latestComment = publicComments[publicComments.length - 1];
  return latestComment?.created_at || ticket.updated_at || ticket.created_at;
}

function getSupportCreatorLabel(ticket: PlannerSupportTicket): string {
  const creatorInfo = ticket.creator_info;
  if (creatorInfo?.company_name) {
    return creatorInfo.company_name;
  }
  const fullName = `${creatorInfo?.first_name || ''} ${creatorInfo?.last_name || ''}`.trim();
  return fullName || creatorInfo?.email || ticket.created_by || 'Support requester';
}

export default function CommunicationsInboxView() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const baseUrl = getApiBaseUrl();
  const requestedWeddingId = searchParams.get('wedding_id') || 'all';
  const requestedTicketId = searchParams.get('ticket_id');
  const requestedConversationRaw = searchParams.get('conversation');
  const requestedConversation = requestedConversationRaw && SUPPORTED_QUERY_CONVERSATIONS.has(requestedConversationRaw as DeepLinkConversation)
    ? requestedConversationRaw as DeepLinkConversation
    : null;
  const invalidConversation = Boolean(
    requestedConversationRaw && !SUPPORTED_QUERY_CONVERSATIONS.has(requestedConversationRaw as DeepLinkConversation)
  );

  const canAccessGuestInbox = canAccessGuestCommunications(userProfile);
  const canAccessCoupleMessages = canMessageCouples(userProfile);
  const canAccessSupportThreads = canAccessSupportInbox(userProfile);
  const currentUserEmail = userProfile?.email?.toLowerCase() || '';

  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string>(() => requestedWeddingId);
  const [showWeddingDropdown, setShowWeddingDropdown] = useState(false);
  const weddingDropdownRef = useRef<HTMLDivElement>(null);

  const [emails, setEmails] = useState<InboundEmail[]>([]);
  const [emailLoading, setEmailLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterUnread, setFilterUnread] = useState(false);

  const [coupleConversations, setCoupleConversations] = useState<CoupleConversationSummary[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);

  const [smsTickets, setSmsTickets] = useState<SMSSupportTicket[]>([]);
  const [supportTickets, setSupportTickets] = useState<PlannerSupportTicket[]>([]);
  const [supportLoading, setSupportLoading] = useState(true);

  const [selectedItem, setSelectedItem] = useState<InboxItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  const [selectedEmailDetail, setSelectedEmailDetail] = useState<InboundEmail | null>(null);
  const [selectedSmsTicketDetail, setSelectedSmsTicketDetail] = useState<SMSSupportTicket | null>(null);
  const [selectedSupportTicketDetail, setSelectedSupportTicketDetail] = useState<PlannerSupportTicket | null>(null);
  const [coupleMessages, setCoupleMessages] = useState<CoupleMessage[]>([]);

  const [replyText, setReplyText] = useState('');
  const [showReply, setShowReply] = useState(false);
  const [sending, setSending] = useState(false);
  const [markSmsResolved, setMarkSmsResolved] = useState(true);

  const [listWidthPercent, setListWidthPercent] = useState(40);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const handledQueryRef = useRef<string | null>(null);

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

  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const response = await fetch(`${baseUrl}/admin/weddings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        const weddingList = Array.isArray(data) ? data : (data.weddings || []);
        setWeddings(weddingList);
      }
    } catch (error) {
      console.error('Failed to fetch weddings:', error);
    }
  }, [baseUrl, token]);

  const fetchEmails = useCallback(async () => {
    if (!token) return;
    if (!canAccessGuestInbox) {
      setEmails([]);
      setPages(0);
      setUnreadCount(0);
      setEmailLoading(false);
      return;
    }

    try {
      setEmailLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '50',
        unread_only: filterUnread.toString(),
      });

      const response = await fetch(`${baseUrl}/admin/inbound-emails/inbox?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        const data: InboxResponse = await response.json();
        setEmails(data.emails);
        setPages(data.pages);
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch inbox:', error);
    } finally {
      setEmailLoading(false);
    }
  }, [baseUrl, canAccessGuestInbox, filterUnread, page, token]);

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
        headers: { Authorization: `Bearer ${token}` },
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
  }, [baseUrl, canAccessCoupleMessages, selectedWeddingId, token]);

  const fetchSupportThreads = useCallback(async () => {
    if (!token) return;
    if (!canAccessSupportThreads) {
      setSmsTickets([]);
      setSupportTickets([]);
      setSupportLoading(false);
      return;
    }

    try {
      setSupportLoading(true);
      const [smsResponse, supportResponse] = await Promise.all([
        fetch(`${baseUrl}/admin/sms-tickets?active_only=true&page=1&limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${baseUrl}/admin/tickets?active_only=true&page=1&limit=100`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (smsResponse.ok) {
        const data: SMSTicketsResponse = await smsResponse.json();
        setSmsTickets(data.tickets || []);
      } else {
        setSmsTickets([]);
      }

      if (supportResponse.ok) {
        const data: SupportTicketsResponse = await supportResponse.json();
        setSupportTickets(data.tickets || []);
      } else {
        setSupportTickets([]);
      }
    } catch (error) {
      console.error('Failed to fetch support threads:', error);
    } finally {
      setSupportLoading(false);
    }
  }, [baseUrl, canAccessSupportThreads, token]);

  useEffect(() => { fetchWeddings(); }, [fetchWeddings]);
  useEffect(() => { fetchEmails(); }, [fetchEmails]);
  useEffect(() => { fetchCoupleConversations(); }, [fetchCoupleConversations]);
  useEffect(() => { fetchSupportThreads(); }, [fetchSupportThreads]);

  const fetchEmailDetail = useCallback(async (emailId: string) => {
    if (!token) return;
    try {
      setDetailLoading(true);
      const response = await fetch(`${baseUrl}/admin/inbound-emails/${emailId}`, {
        headers: { Authorization: `Bearer ${token}` },
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

  const fetchSmsTicketDetail = useCallback(async (ticketId: string): Promise<SMSSupportTicket | null> => {
    if (!token || !canAccessSupportThreads) return null;
    try {
      setDetailLoading(true);
      const response = await fetch(`${baseUrl}/admin/sms-tickets/${ticketId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setQueryError(err.detail || 'This SMS support thread is unavailable.');
        return null;
      }

      const data = await response.json();
      const ticket = data.ticket as SMSSupportTicket;
      if (ticket.source !== 'sms') {
        setQueryError('This SMS support thread is unavailable.');
        return null;
      }
      setSelectedSmsTicketDetail(ticket);
      setSmsTickets((prev) =>
        prev.map((existing) => existing._id === ticketId ? { ...existing, is_read: true } : existing)
      );
      return ticket;
    } catch (error) {
      console.error('Failed to fetch SMS support thread:', error);
      setQueryError('Failed to load the SMS support thread.');
      return null;
    } finally {
      setDetailLoading(false);
    }
  }, [baseUrl, canAccessSupportThreads, token]);

  const fetchSupportTicketDetail = useCallback(async (ticketId: string): Promise<PlannerSupportTicket | null> => {
    if (!token || !canAccessSupportThreads) return null;
    try {
      setDetailLoading(true);
      const response = await fetch(`${baseUrl}/admin/tickets/${ticketId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setQueryError(err.detail || 'This support thread is unavailable.');
        return null;
      }

      const data = await response.json();
      const ticket = data as PlannerSupportTicket;
      if (ticket.source === 'sms') {
        setQueryError('This support thread is unavailable.');
        return null;
      }
      setSelectedSupportTicketDetail(ticket);
      return ticket;
    } catch (error) {
      console.error('Failed to fetch support thread:', error);
      setQueryError('Failed to load the support thread.');
      return null;
    } finally {
      setDetailLoading(false);
    }
  }, [baseUrl, canAccessSupportThreads, token]);

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

  const fetchCoupleMessages = useCallback(async (weddingId: string, options?: { markRead?: boolean }) => {
    if (!token || !canAccessCoupleMessages) return;
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
  }, [baseUrl, canAccessCoupleMessages, markCoupleConversationRead, token]);

  useEffect(() => {
    if (
      (selectedItem?.type === 'couple' && coupleMessages.length > 0) ||
      (selectedItem?.type === 'sms_support' && selectedSmsTicketDetail) ||
      (selectedItem?.type === 'support_ticket' && selectedSupportTicketDetail)
    ) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [coupleMessages, selectedItem, selectedSmsTicketDetail, selectedSupportTicketDetail]);

  useEffect(() => {
    if (selectedItem?.type === 'email' && !canAccessGuestInbox) {
      setSelectedItem(null);
      setSelectedEmailDetail(null);
    }
    if (selectedItem?.type === 'couple' && !canAccessCoupleMessages) {
      setSelectedItem(null);
      setCoupleMessages([]);
    }
    if ((selectedItem?.type === 'sms_support' || selectedItem?.type === 'support_ticket') && !canAccessSupportThreads) {
      setSelectedItem(null);
      setSelectedSmsTicketDetail(null);
      setSelectedSupportTicketDetail(null);
    }
  }, [canAccessCoupleMessages, canAccessGuestInbox, canAccessSupportThreads, selectedItem]);

  const getWeddingLabel = useCallback((weddingId?: string | null): string => {
    if (!weddingId) return '';
    const wedding = weddings.find((item) => item._id === weddingId);
    if (!wedding) return '';
    const partner1 = [wedding.partner1_first_name, wedding.partner1_last_name].filter(Boolean).join(' ');
    const partner2 = [wedding.partner2_first_name, wedding.partner2_last_name].filter(Boolean).join(' ');
    if (partner1 && partner2) return `${partner1} & ${partner2}`;
    return partner1 || partner2 || wedding.slug || weddingId;
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

    for (const ticket of smsTickets) {
      items.push({
        id: `sms_support_${ticket._id}`,
        type: 'sms_support',
        name: getSmsDisplayName(ticket),
        preview: getSmsPreview(ticket),
        is_read: ticket.is_read ?? true,
        created_at: getLatestSmsActivity(ticket),
        wedding_id: ticket.wedding_id || undefined,
        wedding_label: getWeddingLabel(ticket.wedding_id) || ticket.wedding_name || undefined,
        smsSupport: ticket,
      });
    }

    for (const ticket of supportTickets) {
      items.push({
        id: `support_ticket_${ticket._id}`,
        type: 'support_ticket',
        name: ticket.subject || ticket.ticket_number || 'Support ticket',
        preview: getSupportTicketPreview(ticket),
        is_read: true,
        created_at: getSupportTicketActivity(ticket),
        wedding_id: ticket.wedding_id || undefined,
        wedding_label: getWeddingLabel(ticket.wedding_id),
        supportTicket: ticket,
      });
    }

    items.sort((a, b) => {
      if (!a.is_read && b.is_read) return -1;
      if (a.is_read && !b.is_read) return 1;
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return dateB - dateA;
    });

    return items;
  }, [coupleConversations, emails, getWeddingLabel, smsTickets, supportTickets]);

  const allItems = buildUnifiedList();
  const inboxItems = selectedWeddingId === 'all'
    ? allItems
    : allItems.filter((item) => item.wedding_id === selectedWeddingId);
  const filteredItems = filterUnread
    ? inboxItems.filter((item) => !item.is_read)
    : inboxItems;

  const loading = emailLoading || conversationsLoading || supportLoading;
  const smsUnreadCount = smsTickets.reduce(
    (count, ticket) => count + (!ticket.is_read ? 1 : 0),
    0
  );
  const totalUnread = unreadCount + smsUnreadCount + coupleConversations.reduce(
    (count, conversation) => count + (conversation.unread_count || 0),
    0
  );
  const hasAnyInboxAccess = canAccessGuestInbox || canAccessCoupleMessages || canAccessSupportThreads;
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

  const handleSelectItem = useCallback(async (item: InboxItem) => {
    setQueryError(null);
    setSelectedItem(item);
    setShowReply(false);
    setReplyText('');
    setMarkSmsResolved(true);
    setMobileShowDetail(true);
    setSelectedEmailDetail(null);
    setSelectedSmsTicketDetail(null);
    setSelectedSupportTicketDetail(null);
    setCoupleMessages([]);

    if (item.type === 'email' && item.email) {
      await fetchEmailDetail(item.email.id);
      if (!item.email.is_read) {
        setEmails((prev) =>
          prev.map((email) => email.id === item.email?.id ? { ...email, is_read: true } : email)
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
      return;
    }

    if (item.type === 'couple' && item.couple) {
      await fetchCoupleMessages(item.couple.wedding_id, { markRead: true });
      return;
    }

    if (item.type === 'sms_support' && item.smsSupport) {
      await fetchSmsTicketDetail(item.smsSupport._id);
      setSmsTickets((prev) =>
        prev.map((ticket) => ticket._id === item.smsSupport?._id ? { ...ticket, is_read: true } : ticket)
      );
      return;
    }

    if (item.type === 'support_ticket' && item.supportTicket) {
      await fetchSupportTicketDetail(item.supportTicket._id);
    }
  }, [fetchCoupleMessages, fetchEmailDetail, fetchSmsTicketDetail, fetchSupportTicketDetail]);

  const querySelectionKey = `${requestedConversationRaw || ''}|${requestedTicketId || ''}|${requestedWeddingId}`;

  useEffect(() => {
    if (handledQueryRef.current === querySelectionKey) return;
    if (loading) return;

    if (invalidConversation) {
      handledQueryRef.current = querySelectionKey;
      setQueryError(`Unsupported inbox conversation type: ${requestedConversationRaw}`);
      return;
    }

    if (requestedConversation === 'couple') {
      handledQueryRef.current = querySelectionKey;
      setQueryError(null);
      return;
    }

    if (!requestedConversation) {
      handledQueryRef.current = querySelectionKey;
      return;
    }

    if (!canAccessSupportThreads) {
      handledQueryRef.current = querySelectionKey;
      setQueryError('You do not have access to support threads in the inbox.');
      return;
    }

    if (!requestedTicketId) {
      handledQueryRef.current = querySelectionKey;
      setQueryError('This support inbox link is missing a ticket identifier.');
      return;
    }

    const openSupportThread = async () => {
      setQueryError(null);
      handledQueryRef.current = querySelectionKey;

      if (requestedConversation === 'sms_support') {
        const ticket = await fetchSmsTicketDetail(requestedTicketId);
        if (!ticket) return;
        setSelectedItem({
          id: `sms_support_${ticket._id}`,
          type: 'sms_support',
          name: getSmsDisplayName(ticket),
          preview: getSmsPreview(ticket),
          is_read: ticket.is_read ?? true,
          created_at: getLatestSmsActivity(ticket),
          wedding_id: ticket.wedding_id || undefined,
          wedding_label: getWeddingLabel(ticket.wedding_id) || ticket.wedding_name || undefined,
          smsSupport: ticket,
        });
        setMobileShowDetail(true);
        return;
      }

      const ticket = await fetchSupportTicketDetail(requestedTicketId);
      if (!ticket) return;
      setSelectedItem({
        id: `support_ticket_${ticket._id}`,
        type: 'support_ticket',
        name: ticket.subject || ticket.ticket_number || 'Support ticket',
        preview: getSupportTicketPreview(ticket),
        is_read: true,
        created_at: getSupportTicketActivity(ticket),
        wedding_id: ticket.wedding_id || undefined,
        wedding_label: getWeddingLabel(ticket.wedding_id),
        supportTicket: ticket,
      });
      setMobileShowDetail(true);
    };

    void openSupportThread();
  }, [
    canAccessSupportThreads,
    fetchSmsTicketDetail,
    fetchSupportTicketDetail,
    getWeddingLabel,
    invalidConversation,
    loading,
    querySelectionKey,
    requestedConversation,
    requestedConversationRaw,
    requestedTicketId,
    requestedWeddingId,
  ]);

  useEffect(() => {
    if (loading) return;
    if (requestedConversation !== 'couple' || requestedWeddingId === 'all') return;
    const targetConversation = filteredItems.find(
      (item) => item.type === 'couple' && item.wedding_id === requestedWeddingId
    );
    if (!targetConversation) return;
    if (selectedItem?.id === targetConversation.id) return;
    handledQueryRef.current = querySelectionKey;
    void handleSelectItem(targetConversation);
  }, [filteredItems, handleSelectItem, loading, querySelectionKey, requestedConversation, requestedWeddingId, selectedItem?.id]);

  const handleMarkAllRead = async () => {
    if (!token || !canAccessGuestInbox) return;
    try {
      await fetch(`${baseUrl}/admin/inbound-emails/read-all`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      });
      setEmails((prev) => prev.map((email) => ({ ...email, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  const handleSendReply = async () => {
    if (!token || !selectedItem || !replyText.trim()) return;

    if (selectedItem.type === 'email' && selectedItem.email) {
      if (!canAccessGuestInbox) return;
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/admin/inbound-emails/${selectedItem.email.id}/reply`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            html_content: `<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">${replyText.replace(/\n/g, '<br>')}</div>`,
            text_content: replyText,
          }),
        });

        if (response.ok) {
          setReplyText('');
          setShowReply(false);
          setEmails((prev) =>
            prev.map((email) =>
              email.id === selectedItem.email?.id ? { ...email, planner_response_sent: true } : email
            )
          );
        } else {
          const err = await response.json().catch(() => ({}));
          alert(`Failed to send reply: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send reply:', error);
        alert('Failed to send reply. Please try again.');
      } finally {
        setSending(false);
      }
      return;
    }

    if (selectedItem.type === 'couple' && selectedItem.couple) {
      if (!canAccessCoupleMessages) return;
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/couple-portal/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            wedding_id: selectedItem.couple.wedding_id,
            content: replyText,
          }),
        });

        if (response.ok) {
          setReplyText('');
          await fetchCoupleMessages(selectedItem.couple.wedding_id);
          await fetchCoupleConversations();
        } else {
          const err = await response.json().catch(() => ({}));
          alert(`Failed to send message: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send message:', error);
        alert('Failed to send message. Please try again.');
      } finally {
        setSending(false);
      }
      return;
    }

    if (selectedItem.type === 'sms_support' && selectedSmsTicketDetail) {
      if (!canAccessSupportThreads) return;
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/admin/sms-tickets/${selectedSmsTicketDetail._id}/respond`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: replyText,
            mark_resolved: markSmsResolved,
          }),
        });

        if (response.ok) {
          setReplyText('');
          await Promise.all([
            fetchSupportThreads(),
            fetchSmsTicketDetail(selectedSmsTicketDetail._id),
          ]);
        } else {
          const err = await response.json().catch(() => ({}));
          alert(`Failed to send SMS reply: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send SMS reply:', error);
        alert('Failed to send SMS reply. Please try again.');
      } finally {
        setSending(false);
      }
      return;
    }

    if (selectedItem.type === 'support_ticket' && selectedSupportTicketDetail) {
      if (!canAccessSupportThreads) return;
      try {
        setSending(true);
        const response = await fetch(`${baseUrl}/admin/tickets/${selectedSupportTicketDetail._id}/comments`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: replyText,
            is_internal: false,
          }),
        });

        if (response.ok) {
          setReplyText('');
          await Promise.all([
            fetchSupportThreads(),
            fetchSupportTicketDetail(selectedSupportTicketDetail._id),
          ]);
        } else {
          const err = await response.json().catch(() => ({}));
          alert(`Failed to send support reply: ${err.detail || 'Unknown error'}`);
        }
      } catch (error) {
        console.error('Failed to send support reply:', error);
        alert('Failed to send support reply. Please try again.');
      } finally {
        setSending(false);
      }
    }
  };

  const handleRefresh = () => {
    void fetchEmails();
    void fetchCoupleConversations();
    void fetchSupportThreads();
    if (selectedItem?.type === 'couple' && selectedItem.couple) {
      void fetchCoupleMessages(selectedItem.couple.wedding_id, { markRead: true });
    } else if (selectedItem?.type === 'email' && selectedItem.email) {
      void fetchEmailDetail(selectedItem.email.id);
    } else if (selectedItem?.type === 'sms_support' && selectedItem.smsSupport) {
      void fetchSmsTicketDetail(selectedItem.smsSupport._id);
    } else if (selectedItem?.type === 'support_ticket' && selectedItem.supportTicket) {
      void fetchSupportTicketDetail(selectedItem.supportTicket._id);
    }
  };

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
                {selectedEmailDetail.attachments.map((att, index) => (
                  <div
                    key={index}
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

        {canAccessCoupleMessages ? (
          <ChatInput
            value={replyText}
            onChange={setReplyText}
            onSend={handleSendReply}
            sending={sending}
            placeholder={`Message ${coupleName}...`}
            accentColor="rose"
          />
        ) : (
          <div className="border-t border-gray-100 dark:border-slate-800 px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
            You can view this conversation, but you do not have permission to message couples.
          </div>
        )}
      </>
    );
  };

  const renderSmsSupportDetail = () => {
    if (!selectedSmsTicketDetail) return null;

    const isResolved = ['resolved', 'closed'].includes(selectedSmsTicketDetail.status);
    const guestDisplayName = getSmsDisplayName(selectedSmsTicketDetail);
    const responseThread = [
      {
        id: `sms-inbound-${selectedSmsTicketDetail._id}`,
        content: selectedSmsTicketDetail.message,
        senderName: guestDisplayName,
        isSelf: false,
        timestamp: selectedSmsTicketDetail.created_at,
      },
      ...(selectedSmsTicketDetail.responses || []).map((response, index) => ({
        id: `sms-response-${index}-${response.sent_at || index}`,
        content: response.message,
        senderName: response.sent_by_name || response.sent_by || 'Planner',
        isSelf: (response.sent_by || '').toLowerCase() === currentUserEmail,
        timestamp: response.sent_at,
      })),
    ];

    return (
      <>
        <div className="p-4 border-b border-gray-100 dark:border-slate-800">
          <button
            onClick={() => { setMobileShowDetail(false); setSelectedItem(null); setSelectedSmsTicketDetail(null); }}
            className="lg:hidden flex items-center gap-1 text-sm text-gray-500 mb-3"
          >
            <ArrowLeft size={16} />
            Back to inbox
          </button>

          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
              <Smartphone size={16} className="text-indigo-600 dark:text-indigo-300" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {guestDisplayName}
              </h2>
              <p className="text-xs text-gray-400">
                {selectedSmsTicketDetail.phone}
                {selectedSmsTicketDetail.wedding_name ? ` · ${selectedSmsTicketDetail.wedding_name}` : ''}
                {selectedSmsTicketDetail.type === 'help_request' ? ' · HELP request' : ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300">
              SMS Support
            </span>
            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-slate-300">
              {selectedSmsTicketDetail.status.replace('_', ' ')}
            </span>
            <span className="text-xs text-gray-400">
              {formatDate(selectedSmsTicketDetail.created_at)}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {detailLoading ? (
            <div className="text-center text-gray-400 py-8">
              <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
              Loading SMS thread...
            </div>
          ) : (
            responseThread.map((entry) => (
              <MessageBubble
                key={entry.id}
                content={entry.content}
                senderName={!entry.isSelf ? entry.senderName : undefined}
                isSelf={entry.isSelf}
                timestamp={entry.timestamp ? formatDate(entry.timestamp) : undefined}
                accentColor="indigo"
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {canAccessSupportThreads ? (
          <>
            <div className="px-4 pt-3 border-t border-gray-100 dark:border-slate-800 bg-gray-50 dark:bg-slate-800/50">
              <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={markSmsResolved}
                  onChange={(e) => setMarkSmsResolved(e.target.checked)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  disabled={isResolved || sending}
                />
                Mark resolved after send
              </label>
            </div>
            <ChatInput
              value={replyText}
              onChange={setReplyText}
              onSend={handleSendReply}
              sending={sending}
              disabled={isResolved}
              placeholder={isResolved ? 'This SMS support thread is resolved.' : `Reply to ${guestDisplayName}...`}
              accentColor="indigo"
            />
          </>
        ) : (
          <div className="border-t border-gray-100 dark:border-slate-800 px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
            You can view this SMS support thread, but you do not have permission to reply.
          </div>
        )}
      </>
    );
  };

  const renderSupportTicketDetail = () => {
    if (!selectedSupportTicketDetail) return null;

    const publicComments = getPublicSupportComments(selectedSupportTicketDetail);
    const creatorLabel = getSupportCreatorLabel(selectedSupportTicketDetail);
    const isClosed = ['resolved', 'closed'].includes(selectedSupportTicketDetail.status);
    const messages = [
      {
        id: `support-ticket-${selectedSupportTicketDetail._id}`,
        content: selectedSupportTicketDetail.description || selectedSupportTicketDetail.message || selectedSupportTicketDetail.subject,
        senderName: creatorLabel,
        isSelf: (selectedSupportTicketDetail.created_by || '').toLowerCase() === currentUserEmail,
        timestamp: selectedSupportTicketDetail.created_at,
      },
      ...publicComments.map((comment) => ({
        id: comment.id,
        content: comment.message,
        senderName: `${comment.user_info?.first_name || ''} ${comment.user_info?.last_name || ''}`.trim() || comment.user_id,
        isSelf: comment.user_id.toLowerCase() === currentUserEmail,
        timestamp: comment.created_at,
      })),
    ];

    return (
      <>
        <div className="p-4 border-b border-gray-100 dark:border-slate-800">
          <button
            onClick={() => { setMobileShowDetail(false); setSelectedItem(null); setSelectedSupportTicketDetail(null); }}
            className="lg:hidden flex items-center gap-1 text-sm text-gray-500 mb-3"
          >
            <ArrowLeft size={16} />
            Back to inbox
          </button>

          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
              <MessageSquare size={16} className="text-indigo-600 dark:text-indigo-300" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                {selectedSupportTicketDetail.subject}
              </h2>
              <p className="text-xs text-gray-400">
                {selectedSupportTicketDetail.ticket_number || 'Support ticket'} · {creatorLabel}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300">
              Support
            </span>
            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-700 dark:bg-slate-800 dark:text-slate-300">
              {selectedSupportTicketDetail.status.replace('_', ' ')}
            </span>
            <span className="text-xs text-gray-400">
              {formatDate(selectedSupportTicketDetail.created_at)}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {detailLoading ? (
            <div className="text-center text-gray-400 py-8">
              <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
              Loading support thread...
            </div>
          ) : (
            messages.map((entry) => (
              <MessageBubble
                key={entry.id}
                content={entry.content}
                senderName={!entry.isSelf ? entry.senderName : undefined}
                isSelf={entry.isSelf}
                timestamp={entry.timestamp ? formatDate(entry.timestamp) : undefined}
                accentColor="indigo"
              />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {canAccessSupportThreads ? (
          <ChatInput
            value={replyText}
            onChange={setReplyText}
            onSend={handleSendReply}
            sending={sending}
            disabled={isClosed}
            placeholder={isClosed ? 'This support thread is resolved.' : `Reply to ${creatorLabel}...`}
            accentColor="indigo"
          />
        ) : (
          <div className="border-t border-gray-100 dark:border-slate-800 px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
            You can view this support thread, but you do not have permission to reply.
          </div>
        )}
      </>
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox"
        description="All conversations — guest replies, couple messages, SMS support, and support tickets"
      />

      {queryError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <p>{queryError}</p>
          </div>
        </div>
      )}

      <div>
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
                  {weddings.map((wedding) => {
                    const partner1 = [wedding.partner1_first_name, wedding.partner1_last_name].filter(Boolean).join(' ');
                    const partner2 = [wedding.partner2_first_name, wedding.partner2_last_name].filter(Boolean).join(' ');
                    const label = (partner1 && partner2) ? `${partner1} & ${partner2}` : partner1 || partner2 || wedding.slug || wedding._id;
                    return (
                      <button
                        key={wedding._id}
                        onClick={() => { setSelectedWeddingId(wedding._id); setShowWeddingDropdown(false); }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition ${
                          selectedWeddingId === wedding._id ? 'bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-medium' : 'text-gray-700 dark:text-gray-300'
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

        <div ref={containerRef} className="flex h-[calc(100vh-250px)] min-h-[600px] gap-0">
          <div
            className={`bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 overflow-hidden flex flex-col flex-shrink-0 h-full ${mobileShowDetail ? 'hidden lg:block' : ''}`}
            style={{ width: `${listWidthPercent}%` }}
          >
            <div className="flex-1 divide-y divide-gray-100 dark:divide-slate-800 overflow-y-auto">
              {loading ? (
                <div className="p-8 text-center text-gray-400">
                  <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  <p>Loading messages...</p>
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="p-12 text-center text-gray-400">
                  <Inbox className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p className="font-medium mb-1">{hasAnyInboxAccess ? 'No messages' : 'No inbox access'}</p>
                  <p className="text-sm">
                    {!hasAnyInboxAccess
                      ? 'Your role does not include inbox access.'
                      : filterUnread
                        ? 'No unread conversations. Try showing all.'
                        : selectedWeddingId !== 'all'
                          ? 'No conversations for this wedding yet.'
                          : 'Guest replies, couple messages, and support threads will appear here.'}
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
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page <= 1}
                  className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30"
                >
                  Previous
                </button>
                <span className="text-xs text-gray-400">
                  Email page {page} of {pages}
                </span>
                <button
                  onClick={() => setPage((current) => Math.min(pages, current + 1))}
                  disabled={page >= pages}
                  className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </div>

          <div
            onMouseDown={handleMouseDown}
            className="hidden lg:flex items-center justify-center w-3 cursor-col-resize group flex-shrink-0 hover:bg-slate-200/50 dark:hover:bg-slate-700/50 rounded transition-colors mx-0.5"
            title="Drag to resize panels"
          >
            <GripVertical className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 group-hover:text-slate-500 dark:group-hover:text-slate-400 transition-colors" />
          </div>

          <div className={`flex-1 min-w-0 h-full ${!mobileShowDetail ? 'hidden lg:block' : ''}`}>
            {selectedItem ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex flex-col h-full">
                {selectedItem.type === 'email' && selectedEmailDetail
                  ? renderEmailDetail()
                  : selectedItem.type === 'couple'
                    ? renderCoupleChat()
                    : selectedItem.type === 'sms_support' && selectedSmsTicketDetail
                      ? renderSmsSupportDetail()
                      : selectedItem.type === 'support_ticket' && selectedSupportTicketDetail
                        ? renderSupportTicketDetail()
                        : (
                          <div className="flex-1 flex items-center justify-center text-gray-400">
                            <div className="text-center">
                              <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" />
                              <p>Loading...</p>
                            </div>
                          </div>
                        )}
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex items-center justify-center h-full">
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
