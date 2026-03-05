'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
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
  MailOpen
} from 'lucide-react';
import PageHeader from '../components/PageHeader';

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
  // Detail fields
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

// ==================== MAIN PAGE ====================

export default function InboxPage() {
  const { token } = useAdmin();
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

  const [emails, setEmails] = useState<InboundEmail[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmail, setSelectedEmail] = useState<InboundEmail | null>(null);
  const [selectedEmailDetail, setSelectedEmailDetail] = useState<InboundEmail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterUnread, setFilterUnread] = useState(false);
  const [showReply, setShowReply] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  // ==================== DATA FETCHING ====================

  const fetchInbox = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: page.toString(),
        limit: '25',
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
      setLoading(false);
    }
  }, [token, baseUrl, page, filterUnread]);

  useEffect(() => {
    fetchInbox();
  }, [fetchInbox]);

  const fetchEmailDetail = async (emailId: string) => {
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
  };

  // ==================== ACTIONS ====================

  const handleSelectEmail = async (email: InboundEmail) => {
    setSelectedEmail(email);
    setShowReply(false);
    setReplyText('');
    setMobileShowDetail(true);
    await fetchEmailDetail(email.id);

    // Update local state if unread
    if (!email.is_read) {
      setEmails(prev =>
        prev.map(e => e.id === email.id ? { ...e, is_read: true } : e)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    }
  };

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
    if (!token || !selectedEmail || !replyText.trim()) return;
    try {
      setSending(true);
      const response = await fetch(`${baseUrl}/admin/inbound-emails/${selectedEmail.id}/reply`, {
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
        // Update local state
        setEmails(prev =>
          prev.map(e =>
            e.id === selectedEmail.id ? { ...e, planner_response_sent: true } : e
          )
        );
        if (selectedEmail) {
          setSelectedEmail({ ...selectedEmail, planner_response_sent: true });
        }
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
  };

  // ==================== RENDER ====================

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <PageHeader
        title="Inbox"
        description="Guest replies and messages"
      />

      <div className="max-w-7xl mx-auto px-4 pb-6">
        {/* Stats bar */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">
              {total} message{total !== 1 ? 's' : ''}
              {unreadCount > 0 && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700">
                  {unreadCount} unread
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterUnread(!filterUnread)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
                filterUnread
                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400'
                  : 'bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400'
              }`}
            >
              <Filter size={14} />
              {filterUnread ? 'Showing unread' : 'All messages'}
            </button>

            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400 transition"
              >
                <CheckCheck size={14} />
                Mark all read
              </button>
            )}

            <button
              onClick={fetchInbox}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-600 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-400 transition"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Main content area */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">

          {/* Email List Panel */}
          <div className={`lg:col-span-2 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 overflow-hidden ${mobileShowDetail ? 'hidden lg:block' : ''}`}>
            <div className="divide-y divide-gray-100 dark:divide-slate-800 max-h-[calc(100vh-250px)] overflow-y-auto">
              {loading ? (
                <div className="p-8 text-center text-gray-400">
                  <RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  <p>Loading messages...</p>
                </div>
              ) : emails.length === 0 ? (
                <div className="p-12 text-center text-gray-400">
                  <Inbox className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p className="font-medium mb-1">No messages yet</p>
                  <p className="text-sm">
                    {filterUnread
                      ? 'No unread messages. Try showing all messages.'
                      : 'When guests reply to your emails, their messages will appear here.'}
                  </p>
                </div>
              ) : (
                emails.map((email) => (
                  <div
                    key={email.id}
                    onClick={() => handleSelectEmail(email)}
                    className={`px-4 py-3 cursor-pointer transition-colors border-l-3 ${
                      selectedEmail?.id === email.id
                        ? 'bg-rose-50 dark:bg-rose-900/10 border-l-rose-500'
                        : email.is_read
                          ? 'border-l-transparent hover:bg-gray-50 dark:hover:bg-slate-800/50'
                          : 'border-l-rose-400 bg-rose-50/50 dark:bg-rose-900/5 hover:bg-rose-50 dark:hover:bg-rose-900/10'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Unread indicator */}
                      <div className="mt-2 flex-shrink-0">
                        {!email.is_read ? (
                          <div className="w-2.5 h-2.5 bg-rose-500 rounded-full" />
                        ) : (
                          <div className="w-2.5 h-2.5" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        {/* Sender + time */}
                        <div className="flex items-center justify-between gap-2 mb-0.5">
                          <p className={`text-sm truncate ${!email.is_read ? 'font-semibold text-gray-900 dark:text-white' : 'font-medium text-gray-700 dark:text-gray-300'}`}>
                            {email.guest_name || email.from_name || email.from_address}
                          </p>
                          <span className="text-xs text-gray-400 flex-shrink-0">
                            {formatDate(email.created_at)}
                          </span>
                        </div>

                        {/* Subject */}
                        <p className={`text-sm truncate mb-0.5 ${!email.is_read ? 'text-gray-800 dark:text-gray-200' : 'text-gray-600 dark:text-gray-400'}`}>
                          {email.subject}
                        </p>

                        {/* Preview */}
                        <p className="text-xs text-gray-400 line-clamp-1">
                          {email.preview}
                        </p>

                        {/* Badges */}
                        <div className="flex items-center gap-2 mt-1">
                          {email.has_attachments && (
                            <span className="inline-flex items-center gap-0.5 text-xs text-gray-400">
                              <Paperclip size={10} />
                            </span>
                          )}
                          {email.planner_response_sent && (
                            <span className="inline-flex items-center gap-0.5 text-xs text-emerald-500">
                              <Reply size={10} />
                              Replied
                            </span>
                          )}
                          {email.wedding_slug && (
                            <span className="text-xs text-gray-400 bg-gray-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">
                              {email.wedding_slug}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Pagination */}
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

          {/* Email Detail Panel */}
          <div className={`lg:col-span-3 ${!mobileShowDetail ? 'hidden lg:block' : ''}`}>
            {selectedEmail && selectedEmailDetail ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex flex-col h-[calc(100vh-250px)]">

                {/* Header */}
                <div className="p-4 border-b border-gray-100 dark:border-slate-800">
                  {/* Mobile back button */}
                  <button
                    onClick={() => { setMobileShowDetail(false); setSelectedEmail(null); setSelectedEmailDetail(null); }}
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

                {/* Content */}
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
                        onClick={() => fetchEmailDetail(selectedEmail.id)}
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

                  {/* Attachments */}
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

                {/* Reply Section */}
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
              </div>
            ) : (
              <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 flex items-center justify-center h-[calc(100vh-250px)]">
                <div className="text-center text-gray-400">
                  <Mail className="w-14 h-14 mx-auto mb-4 opacity-30" />
                  <p className="font-medium text-gray-500 dark:text-gray-400">Select a message to read</p>
                  <p className="text-sm mt-1">Choose an email from the list to view its contents</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
