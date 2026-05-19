'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';
import { Card } from '@/components/ui/Card';
import PageHeader from '../components/PageHeader';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import {
  MessageSquare,
  Clock,
  CheckCircle,
  AlertCircle,
  Users,
  TrendingUp,
  Search,
  Filter,
  RefreshCw,
  Send,
  X,
  Plus,
  Loader2
} from 'lucide-react';
import KnowledgeBase from '../components/kb/KnowledgeBase';
import BlogManager from '../components/blog/BlogManager';

interface SupportTicket {
  _id: string;
  ticket_number?: string;
  user_id: string;
  user_email?: string;
  created_by?: string;
  user_name?: string;
  subject: string;
  description?: string;
  message?: string;
  wedding_id?: string;
  category: 'technical' | 'billing' | 'feature_request' | 'bug_report' | 'general';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  created_at: string;
  updated_at: string;
  response_count?: number;
  comment_count?: number;
  creator_info?: {
    first_name?: string;
    last_name?: string;
    company_name?: string;
  };
}

interface SupportMetrics {
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets?: number;
  resolved_today: number;
  avg_resolution_time_hours: number;
  urgent_tickets?: number;
}

interface TicketCountResponse {
  total?: number;
}

interface SmsSupportSummary {
  total?: number;
  urgent_count?: number;
  by_status?: {
    new?: number;
    in_progress?: number;
    resolved?: number;
  };
}

type SupportTab = 'tickets' | 'metrics' | 'knowledge_base' | 'blog';

function normalizeSupportTab(tab: string | null, isRootAdmin: boolean): SupportTab {
  if (tab === 'knowledge_base') return 'knowledge_base';
  if (isRootAdmin && (tab === 'metrics' || tab === 'blog')) return tab;
  return 'tickets';
}

export default function SupportPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchParamsText = searchParams.toString();
  const { apiRequest, userProfile } = useAdmin();
  const [activeTab, setActiveTab] = useState<SupportTab>('tickets');
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [metrics, setMetrics] = useState<SupportMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTicket, setNewTicket] = useState({
    subject: '',
    description: '',
    category: 'general' as const,
    priority: 'medium' as const
  });

  const pagination = usePagination({ initialItemsPerPage: 50 });
  const {
    currentPage,
    itemsPerPage,
    setTotalItems: setPaginationTotalItems,
  } = pagination;

  const isRootAdmin = userProfile?.is_root_admin;

  useEffect(() => {
    const params = new URLSearchParams(searchParamsText);
    setActiveTab(normalizeSupportTab(params.get('tab'), Boolean(isRootAdmin)));
  }, [isRootAdmin, searchParamsText]);

  const handleTabChange = useCallback((tab: SupportTab) => {
    const params = new URLSearchParams(searchParamsText);
    params.set('tab', tab);
    if (tab !== 'blog') {
      params.delete('blogArticle');
      params.delete('blogMode');
    }

    setActiveTab(tab);
    router.replace(`/admin/support?${params.toString()}`, { scroll: false });
  }, [router, searchParamsText]);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      let fetchedTickets: SupportTicket[] = [];
      let fetchedTicketTotal = 0;

      // Fetch support tickets
      try {
        const endpoint = isRootAdmin ? '/admin/tickets' : '/admin/my-tickets';
        const url = `${endpoint}?page=${currentPage}&limit=${itemsPerPage}`;
        const ticketsResponse = await apiRequest<{ tickets: SupportTicket[], total?: number, page?: number }>(
          url,
          'GET'
        );
        fetchedTickets = ticketsResponse?.tickets ?? [];
        fetchedTicketTotal = ticketsResponse?.total || fetchedTickets.length;
        setTickets(fetchedTickets);
        setPaginationTotalItems(fetchedTicketTotal);
      } catch (error) {
        console.warn('Support tickets endpoint not available');
        setTickets([]);
      }

      // Fetch metrics (ROOT_ADMIN only)
      if (isRootAdmin) {
        try {
          const [metricsResponse, analyticsResponse] = await Promise.all([
            apiRequest<{
              open_tickets?: number;
              in_progress_tickets?: number;
              resolved_today?: number;
              urgent_tickets?: number;
            }>('/admin/metrics/dashboard', 'GET'),
            apiRequest<{
              total_tickets?: number;
              avg_resolution_time_hours?: number;
            }>('/admin/analytics?period=30d', 'GET'),
          ]);

          setMetrics({
            total_tickets: analyticsResponse?.total_tickets ?? fetchedTicketTotal,
            open_tickets: metricsResponse?.open_tickets ?? fetchedTickets.filter(t => t.status === 'open').length,
            in_progress_tickets: metricsResponse?.in_progress_tickets ?? fetchedTickets.filter(t => t.status === 'in_progress').length,
            resolved_today: metricsResponse?.resolved_today ?? 0,
            avg_resolution_time_hours: analyticsResponse?.avg_resolution_time_hours ?? 0,
            urgent_tickets: metricsResponse?.urgent_tickets ?? 0,
          });
        } catch (error) {
          console.warn('Support metrics endpoint not available');
          try {
            const [openResponse, inProgressResponse, urgentResponse, smsSummary] = await Promise.all([
              apiRequest<TicketCountResponse>('/admin/tickets?status=open&page=1&limit=1', 'GET'),
              apiRequest<TicketCountResponse>('/admin/tickets?status=in_progress&page=1&limit=1', 'GET'),
              apiRequest<TicketCountResponse>('/admin/tickets?priority=urgent&page=1&limit=1', 'GET'),
              apiRequest<SmsSupportSummary>('/admin/sms-tickets/stats/summary', 'GET'),
            ]);

            setMetrics({
              total_tickets: fetchedTicketTotal + (smsSummary?.total ?? 0),
              open_tickets: (openResponse?.total ?? 0) + (smsSummary?.by_status?.new ?? 0),
              in_progress_tickets: (inProgressResponse?.total ?? 0) + (smsSummary?.by_status?.in_progress ?? 0),
              resolved_today: 0,
              avg_resolution_time_hours: 0,
              urgent_tickets: (urgentResponse?.total ?? 0) + (smsSummary?.urgent_count ?? 0),
            });
          } catch (fallbackError) {
            console.warn('Support metrics fallback counts not available', fallbackError);
            setMetrics({
              total_tickets: fetchedTicketTotal,
              open_tickets: fetchedTickets.filter(t => t.status === 'open').length,
              in_progress_tickets: fetchedTickets.filter(t => t.status === 'in_progress').length,
              resolved_today: 0,
              avg_resolution_time_hours: 0,
              urgent_tickets: fetchedTickets.filter(t => t.priority === 'urgent' && ['open', 'in_progress'].includes(t.status)).length,
            });
          }
        }
      }
    } catch (error) {
      console.error('Error fetching support data:', error);
      setTickets([]);
      setMetrics(null);
    } finally {
      setLoading(false);
    }
  }, [apiRequest, isRootAdmin, currentPage, itemsPerPage, setPaginationTotalItems]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const updateTicketStatus = async (ticketId: string, newStatus: SupportTicket['status']) => {
    try {
      await apiRequest(`/admin/tickets/${ticketId}`, 'PUT', { status: newStatus });

      setTickets(tickets.map(ticket =>
        ticket._id === ticketId ? { ...ticket, status: newStatus, updated_at: new Date().toISOString() } : ticket
      ));
    } catch (error) {
      console.error('Error updating ticket status:', error);
      alert('Failed to update ticket status');
    }
  };

  const openTicketInInbox = useCallback((ticket: SupportTicket) => {
    const params = new URLSearchParams({
      conversation: 'support_ticket',
      ticket_id: ticket._id,
    });
    if (ticket.wedding_id) {
      params.set('wedding_id', ticket.wedding_id);
    }
    router.push(`/admin/communications/inbox?${params.toString()}`);
  }, [router]);

  const createTicket = async () => {
    if (!newTicket.subject.trim() || !newTicket.description.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      setCreating(true);
      const result = await apiRequest<{ id: string; ticket_number: string; message: string }>('/admin/tickets', 'POST', newTicket);

      // Validate the response contains expected fields
      if (!result || !result.ticket_number) {
        throw new Error('Failed to create ticket - invalid response from server');
      }

      // Reset form and close modal
      setNewTicket({
        subject: '',
        description: '',
        category: 'general',
        priority: 'medium'
      });
      setShowCreateModal(false);

      // Refresh tickets list - await to ensure list updates before showing success
      await fetchData();

      alert(`Support ticket ${result.ticket_number} created successfully! Our team will respond soon.`);
    } catch (error) {
      console.error('Error creating ticket:', error);
      alert('Failed to create support ticket. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  const filteredTickets = tickets.filter(ticket => {
    const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter;
    const matchesPriority = priorityFilter === 'all' || ticket.priority === priorityFilter;
    const matchesSearch = searchQuery === '' ||
      ticket.subject?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.created_by?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.ticket_number?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesPriority && matchesSearch;
  });

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
      case 'high': return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300';
      case 'resolved': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      case 'closed': return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
      default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'technical': return '🔧';
      case 'billing': return '💳';
      case 'feature_request': return '💡';
      case 'bug_report': return '🐛';
      case 'general': return '💬';
      default: return '📧';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading support data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Support Center"
        description={isRootAdmin ? 'Manage user support tickets and help resources' : 'View and manage your support tickets'}
      >
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
        {!isRootAdmin && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Ticket
          </button>
        )}
      </PageHeader>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-8">
          {[
            { key: 'tickets', label: 'Support Tickets' },
            ...(isRootAdmin ? [{ key: 'metrics', label: 'Support Metrics' }] : []),
            { key: 'knowledge_base', label: 'Knowledge Base' },
            ...(isRootAdmin ? [{ key: 'blog', label: 'Blog' }] : []),
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key as SupportTab)}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Support Tickets Tab */}
      {activeTab === 'tickets' && (
        <div className="space-y-6">
          {/* Filters */}
          <Card className="p-4">
            <div className="flex flex-col sm:flex-row gap-4">
              {/* Search */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search tickets..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    pagination.setPage(1);
                  }}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  pagination.setPage(1);
                }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Statuses</option>
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>

              {/* Priority Filter */}
              <select
                value={priorityFilter}
                onChange={(e) => {
                  setPriorityFilter(e.target.value);
                  pagination.setPage(1);
                }}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </Card>

          {/* Compact Pagination */}
          <GlassPagination
            currentPage={pagination.currentPage}
            totalPages={pagination.totalPages}
            totalItems={pagination.totalItems}
            itemsPerPage={pagination.itemsPerPage}
            onPageChange={pagination.setPage}
            variant="compact"
            itemLabel="tickets"
          />

          {/* Tickets Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-slate-700 border-b border-gray-200 dark:border-slate-600">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Ticket
                    </th>
                    {isRootAdmin && (
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        User
                      </th>
                    )}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Priority
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                  {filteredTickets.map((ticket) => (
                    <tr key={ticket._id} className="hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-start space-x-3">
                          <span className="text-lg">{getCategoryIcon(ticket.category)}</span>
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {ticket.subject}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                              {ticket.ticket_number || ticket.category.replace('_', ' ')}
                            </div>
                          </div>
                        </div>
                      </td>
                      {isRootAdmin && (
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {ticket.creator_info?.company_name ||
                               `${ticket.creator_info?.first_name || ''} ${ticket.creator_info?.last_name || ''}`.trim() ||
                               ticket.user_name ||
                               'Unknown User'}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                              {ticket.created_by || ticket.user_email}
                            </div>
                          </div>
                        </td>
                      )}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getPriorityColor(ticket.priority)}`}>
                          {ticket.priority}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(ticket.status)}`}>
                          {ticket.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {formatDate(ticket.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => openTicketInInbox(ticket)}
                            className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                          >
                            Open in Inbox
                          </button>
                          {isRootAdmin && ticket.status !== 'resolved' && (
                            <button
                              onClick={() => updateTicketStatus(ticket._id, 'resolved')}
                              className="text-green-600 dark:text-green-400 hover:text-green-800 dark:hover:text-green-300"
                            >
                              Resolve
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <GlassPagination
            currentPage={pagination.currentPage}
            totalPages={pagination.totalPages}
            totalItems={pagination.totalItems}
            itemsPerPage={pagination.itemsPerPage}
            onPageChange={pagination.setPage}
            onItemsPerPageChange={pagination.setItemsPerPage}
            itemLabel="tickets"
          />

          {filteredTickets.length === 0 && (
            <div className="text-center py-12">
              <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No tickets found</h3>
              <p className="text-gray-500 dark:text-gray-400">
                {searchQuery || statusFilter !== 'all' || priorityFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'No support tickets have been submitted yet'}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Support Metrics Tab */}
      {activeTab === 'metrics' && isRootAdmin && metrics && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Support Performance</h2>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Tickets</h3>
                  <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{metrics.total_tickets}</p>
                </div>
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <MessageSquare className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Open Tickets</h3>
                  <p className="text-3xl font-bold text-orange-600 dark:text-orange-400 mt-1">{metrics.open_tickets}</p>
                </div>
                <div className="p-3 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Resolved Today</h3>
                  <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-1">{metrics.resolved_today}</p>
                </div>
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">In Progress</h3>
                  <p className="text-3xl font-bold text-yellow-600 dark:text-yellow-400 mt-1">{metrics.in_progress_tickets || 0}</p>
                </div>
                <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                  <Clock className="w-6 h-6 text-yellow-600 dark:text-yellow-400" />
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg Resolution</h3>
                  <p className="text-3xl font-bold text-purple-600 dark:text-purple-400 mt-1">{metrics.avg_resolution_time_hours.toFixed(1)}h</p>
                </div>
                <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                  <TrendingUp className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Knowledge Base Tab */}
      {activeTab === 'knowledge_base' && (
        <KnowledgeBase isRootAdmin={isRootAdmin || false} />
      )}

      {/* Blog Tab */}
      {activeTab === 'blog' && isRootAdmin && (
        <BlogManager />
      )}

      {/* Create Ticket Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-lg w-full max-w-lg shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-slate-700">
              <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                  Create Support Ticket
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Describe your issue and we&apos;ll get back to you soon
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {/* Subject */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Subject <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newTicket.subject}
                  onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
                  placeholder="Brief description of your issue"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Category & Priority */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Category
                  </label>
                  <select
                    value={newTicket.category}
                    onChange={(e) => setNewTicket({ ...newTicket, category: e.target.value as any })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="general">General</option>
                    <option value="technical">Technical Issue</option>
                    <option value="billing">Billing</option>
                    <option value="feature_request">Feature Request</option>
                    <option value="bug_report">Bug Report</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Priority
                  </label>
                  <select
                    value={newTicket.priority}
                    onChange={(e) => setNewTicket({ ...newTicket, priority: e.target.value as any })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={newTicket.description}
                  onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                  placeholder="Please describe your issue in detail..."
                  rows={5}
                  className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 dark:border-slate-700">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createTicket}
                disabled={creating || !newTicket.subject.trim() || !newTicket.description.trim()}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Submit Ticket
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
