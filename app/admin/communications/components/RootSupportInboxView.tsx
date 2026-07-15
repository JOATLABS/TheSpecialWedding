'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowLeft, Inbox, MessageSquare, RefreshCw } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

import PageHeader from '../../components/PageHeader';
import ChatInput from '@/components/ui/ChatInput';
import InboxListItem from '@/components/ui/InboxListItem';
import MessageBubble from '@/components/ui/MessageBubble';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';
import { getApiBaseUrl } from '@/utils/env';

type StatusFilter = 'active' | 'all' | 'resolved' | 'closed';

interface SupportComment {
  id: string;
  message: string;
  user_id: string;
  is_internal?: boolean;
  created_at: string;
  user_info?: {
    first_name?: string;
    last_name?: string;
    email?: string;
  };
}

interface SupportTicket {
  _id: string;
  ticket_number?: string;
  subject: string;
  description?: string;
  message?: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority?: string;
  category?: string;
  created_by: string;
  created_at: string;
  updated_at?: string;
  is_read: boolean;
  comments?: SupportComment[];
  creator_info?: {
    first_name?: string;
    last_name?: string;
    company_name?: string;
    email?: string;
  };
}

interface TicketsResponse {
  tickets: SupportTicket[];
  total: number;
  page: number;
  pages: number;
  unread_count: number;
}

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'active', label: 'Active' },
  { value: 'all', label: 'All' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

function publicComments(ticket: SupportTicket): SupportComment[] {
  return (ticket.comments || []).filter((comment) => !comment.is_internal);
}

function creatorLabel(ticket: SupportTicket): string {
  if (ticket.creator_info?.company_name) return ticket.creator_info.company_name;
  const fullName = `${ticket.creator_info?.first_name || ''} ${ticket.creator_info?.last_name || ''}`.trim();
  return fullName || ticket.creator_info?.email || ticket.created_by || 'Support requester';
}

function ticketPreview(ticket: SupportTicket): string {
  const comments = publicComments(ticket);
  return comments.at(-1)?.message || ticket.description || ticket.message || ticket.subject;
}

function latestActivity(ticket: SupportTicket): string {
  const comments = publicComments(ticket);
  return comments.at(-1)?.created_at || ticket.updated_at || ticket.created_at;
}

export default function RootSupportInboxView() {
  const { token, userProfile } = useAdmin();
  const searchParams = useSearchParams();
  const baseUrl = getApiBaseUrl();
  const requestedConversation = searchParams.get('conversation');
  const requestedTicketId = searchParams.get('ticket_id');
  const handledDeepLink = useRef<string | null>(null);

  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTickets = useCallback(async () => {
    if (!token) return;
    const params = new URLSearchParams({ page: page.toString(), limit: '50' });
    if (statusFilter === 'active') params.set('active_only', 'true');
    if (statusFilter === 'resolved' || statusFilter === 'closed') {
      params.set('status', statusFilter);
    }

    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${baseUrl}/admin/tickets?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to load support tickets.');
      }
      const data = await response.json() as TicketsResponse;
      setTickets(data.tickets || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
      setUnreadCount(data.unread_count || 0);
    } catch (fetchError) {
      console.error('Failed to load root support inbox:', fetchError);
      setTickets([]);
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load support tickets.');
    } finally {
      setLoading(false);
    }
  }, [baseUrl, page, statusFilter, token]);

  const fetchTicket = useCallback(async (ticketId: string) => {
    if (!token) return null;
    try {
      setDetailLoading(true);
      setError(null);
      const response = await fetch(`${baseUrl}/admin/tickets/${ticketId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'This support ticket is unavailable.');
      }
      const ticket = await response.json() as SupportTicket;
      setSelectedTicket(ticket);
      setTickets((current) => current.map((item) => (
        item._id === ticketId ? { ...item, is_read: true } : item
      )));
      setUnreadCount((current) => Math.max(0, current - (
        tickets.find((item) => item._id === ticketId && !item.is_read) ? 1 : 0
      )));
      setMobileShowDetail(true);
      return ticket;
    } catch (fetchError) {
      console.error('Failed to load root support ticket:', fetchError);
      setSelectedTicket(null);
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load this support ticket.');
      return null;
    } finally {
      setDetailLoading(false);
    }
  }, [baseUrl, tickets, token]);

  useEffect(() => {
    void fetchTickets();
  }, [fetchTickets]);

  useEffect(() => {
    if (loading) return;
    if (!requestedConversation && !requestedTicketId) return;
    const deepLinkKey = `${requestedConversation || ''}:${requestedTicketId || ''}`;
    if (handledDeepLink.current === deepLinkKey) return;
    handledDeepLink.current = deepLinkKey;

    if (requestedConversation !== 'support_ticket' || !requestedTicketId) {
      setError('Root administrators can open platform support conversations only.');
      return;
    }
    void fetchTicket(requestedTicketId);
  }, [fetchTicket, loading, requestedConversation, requestedTicketId]);

  const sortedTickets = useMemo(
    () => [...tickets].sort((a, b) => {
      return new Date(latestActivity(b)).getTime() - new Date(latestActivity(a)).getTime();
    }),
    [tickets],
  );

  const handleSend = async () => {
    if (!token || !selectedTicket || !replyText.trim()) return;
    try {
      setSending(true);
      setError(null);
      const response = await fetch(`${baseUrl}/admin/tickets/${selectedTicket._id}/comments`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: replyText.trim(), is_internal: false }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to send support reply.');
      }
      setReplyText('');
      await Promise.all([fetchTicket(selectedTicket._id), fetchTickets()]);
    } catch (sendError) {
      console.error('Failed to send root support reply:', sendError);
      setError(sendError instanceof Error ? sendError.message : 'Failed to send support reply.');
    } finally {
      setSending(false);
    }
  };

  const comments = selectedTicket ? publicComments(selectedTicket) : [];
  const closed = selectedTicket ? ['resolved', 'closed'].includes(selectedTicket.status) : false;
  const currentEmail = userProfile?.email?.toLowerCase() || '';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inbox"
        description="Platform support conversations addressed to the root administrator"
      />

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {total} authorized support ticket{total === 1 ? '' : 's'}
          {unreadCount > 0 ? ` · ${unreadCount} unread on this page` : ''}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => { setStatusFilter(filter.value); setPage(1); }}
              className={`rounded-lg px-3 py-1.5 text-sm transition ${
                statusFilter === filter.value
                  ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300'
                  : 'bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400'
              }`}
            >
              {filter.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => void fetchTickets()}
            aria-label="Refresh support inbox"
            className="rounded-lg bg-white p-2 text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="flex h-[calc(100svh-250px)] min-h-[560px] min-w-0 gap-3">
        <div className={`flex h-full w-full flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900 lg:w-[40%] ${mobileShowDetail ? 'hidden lg:flex' : ''}`}>
          <div className="scrollbar-visible-thin flex-1 divide-y divide-gray-100 overflow-y-auto dark:divide-slate-800">
            {loading ? (
              <div className="p-10 text-center text-gray-400">
                <RefreshCw className="mx-auto mb-2 h-6 w-6 animate-spin" />
                Loading support tickets...
              </div>
            ) : sortedTickets.length === 0 ? (
              <div className="p-12 text-center text-gray-400">
                <Inbox className="mx-auto mb-3 h-12 w-12 opacity-40" />
                <p className="font-medium">No support tickets</p>
                <p className="mt-1 text-sm">No tickets match this status filter.</p>
              </div>
            ) : sortedTickets.map((ticket) => (
              <InboxListItem
                key={ticket._id}
                id={ticket._id}
                type="support_ticket"
                name={ticket.subject || ticket.ticket_number || 'Support ticket'}
                preview={ticketPreview(ticket)}
                isRead={ticket.is_read}
                isSelected={selectedTicket?._id === ticket._id}
                timestamp={formatDate(latestActivity(ticket))}
                accentColor="indigo"
                onClick={() => void fetchTicket(ticket._id)}
              />
            ))}
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between border-t border-gray-100 p-3 text-sm dark:border-slate-800">
              <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="text-gray-600 disabled:opacity-30 dark:text-gray-400">
                Previous
              </button>
              <span className="text-xs text-gray-400">Page {page} of {pages}</span>
              <button type="button" disabled={page >= pages} onClick={() => setPage((value) => Math.min(pages, value + 1))} className="text-gray-600 disabled:opacity-30 dark:text-gray-400">
                Next
              </button>
            </div>
          )}
        </div>

        <div className={`h-full min-w-0 flex-1 ${mobileShowDetail ? 'block' : 'hidden lg:block'}`}>
          {selectedTicket ? (
            <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="border-b border-gray-100 p-4 dark:border-slate-800">
                <button type="button" onClick={() => { setMobileShowDetail(false); setSelectedTicket(null); }} className="mb-3 flex items-center gap-1 text-sm text-gray-500 lg:hidden">
                  <ArrowLeft className="h-4 w-4" /> Back to inbox
                </button>
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/30">
                    <MessageSquare className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="truncate text-lg font-semibold text-gray-900 dark:text-white">{selectedTicket.subject}</h2>
                    <p className="text-xs text-gray-400">{selectedTicket.ticket_number || 'Support ticket'} · {creatorLabel(selectedTicket)}</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-indigo-50 px-2 py-1 font-semibold text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300">Platform Support</span>
                  <span className="rounded-full bg-gray-100 px-2 py-1 font-semibold text-gray-700 dark:bg-slate-800 dark:text-slate-300">{selectedTicket.status.replace('_', ' ')}</span>
                  {selectedTicket.priority && <span className="text-gray-400">{selectedTicket.priority} priority</span>}
                </div>
              </div>

              <div className="scrollbar-visible-thin min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                {detailLoading ? (
                  <div className="py-8 text-center text-gray-400"><RefreshCw className="mx-auto h-5 w-5 animate-spin" /></div>
                ) : (
                  <>
                    <MessageBubble
                      content={selectedTicket.description || selectedTicket.message || selectedTicket.subject}
                      senderName={creatorLabel(selectedTicket)}
                      isSelf={selectedTicket.created_by.toLowerCase() === currentEmail}
                      timestamp={formatDate(selectedTicket.created_at)}
                      accentColor="indigo"
                    />
                    {comments.map((comment) => {
                      const self = comment.user_id.toLowerCase() === currentEmail;
                      const name = `${comment.user_info?.first_name || ''} ${comment.user_info?.last_name || ''}`.trim() || comment.user_info?.email || comment.user_id;
                      return (
                        <MessageBubble
                          key={comment.id}
                          content={comment.message}
                          senderName={self ? undefined : name}
                          isSelf={self}
                          timestamp={formatDate(comment.created_at)}
                          accentColor="indigo"
                        />
                      );
                    })}
                  </>
                )}
              </div>

              <ChatInput
                value={replyText}
                onChange={setReplyText}
                onSend={handleSend}
                sending={sending}
                disabled={closed}
                placeholder={closed ? 'This support ticket is closed.' : `Reply to ${creatorLabel(selectedTicket)}...`}
                accentColor="indigo"
              />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl border border-gray-200 bg-white text-gray-400 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="text-center"><Inbox className="mx-auto mb-3 h-12 w-12 opacity-30" /><p>Select a support ticket</p></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
