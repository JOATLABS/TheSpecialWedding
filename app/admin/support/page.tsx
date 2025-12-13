'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';

interface SupportTicket {
  _id: string;
  user_id: string;
  user_email: string;
  user_name?: string;
  subject: string;
  message: string;
  category: 'technical' | 'billing' | 'feature_request' | 'bug_report' | 'general';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  created_at: string;
  updated_at: string;
  response_count: number;
}

interface SupportMetrics {
  total_tickets: number;
  open_tickets: number;
  resolved_today: number;
  avg_response_time: number;
  satisfaction_score: number;
}

export default function SupportPage() {
  const { apiRequest } = useAdmin();
  const [activeTab, setActiveTab] = useState<'tickets' | 'metrics' | 'knowledge_base'>('tickets');
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [metrics, setMetrics] = useState<SupportMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [responseMessage, setResponseMessage] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      // Try to fetch from actual API endpoints, fall back to empty arrays
      try {
        // Fetch support tickets from backend
        const ticketsResponse = await apiRequest<{ tickets: SupportTicket[] }>('/admin/tickets', 'GET');
        setTickets(ticketsResponse?.tickets ?? []);
      } catch (error) {
        console.warn('Support tickets endpoint not available, using empty array');
        setTickets([]);
      }

      try {
        const metricsResponse = await apiRequest<SupportMetrics>('/admin/analytics', 'GET');
        setMetrics(metricsResponse ?? {
          total_tickets: 0,
          open_tickets: 0,
          resolved_today: 0,
          avg_response_time: 0,
          satisfaction_score: 0
        });
      } catch (error) {
        console.warn('Support metrics endpoint not available, using defaults');
        setMetrics({
          total_tickets: 0,
          open_tickets: 0,
          resolved_today: 0,
          avg_response_time: 0,
          satisfaction_score: 0
        });
      }
    } catch (error) {
      console.error('Error fetching support data:', error);
      setTickets([]);
      setMetrics({
        total_tickets: 0,
        open_tickets: 0,
        resolved_today: 0,
        avg_response_time: 0,
        satisfaction_score: 0
      });
    } finally {
      setLoading(false);
    }
  }, [apiRequest]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);


  const updateTicketStatus = async (ticketId: string, newStatus: SupportTicket['status']) => {
    try {
      await apiRequest(`/tickets/${ticketId}`, 'PUT', { status: newStatus });

      setTickets(tickets.map(ticket =>
        ticket._id === ticketId ? { ...ticket, status: newStatus, updated_at: new Date().toISOString() } : ticket
      ));
    } catch (error) {
      console.error('Error updating ticket status:', error);
      alert('Failed to update ticket status');
    }
  };

  const sendResponse = async () => {
    if (!selectedTicket || !responseMessage.trim()) {
      alert('Please enter a response message');
      return;
    }

    try {
      await apiRequest(`/tickets/${selectedTicket._id}/comments`, 'POST', {
        message: responseMessage,
        is_internal: false
      });

      // Update ticket in local state
      setTickets(tickets.map(ticket =>
        ticket._id === selectedTicket._id
          ? {
              ...ticket,
              status: 'in_progress',
              response_count: ticket.response_count + 1,
              updated_at: new Date().toISOString()
            }
          : ticket
      ));

      setResponseMessage('');
      setSelectedTicket(null);
      alert('Response sent successfully!');
    } catch (error) {
      console.error('Error sending response:', error);
      alert('Failed to send response');
    }
  };

  const filteredTickets = tickets.filter(ticket => {
    const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter;
    const matchesPriority = priorityFilter === 'all' || ticket.priority === priorityFilter;
    return matchesStatus && matchesPriority;
  });

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800';
      case 'resolved': return 'bg-green-100 text-green-800';
      case 'closed': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
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
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg">Loading support data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-heading text-wedding-rose">Support Center</h1>
        <p className="text-gray-600 dark:text-gray-400">Manage user support tickets and help resources</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex space-x-8">
          {[
            { key: 'tickets', label: 'Support Tickets' },
            { key: 'metrics', label: 'Support Metrics' },
            { key: 'knowledge_base', label: 'Knowledge Base' }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.key
                  ? 'border-wedding-rose text-wedding-rose'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
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
          <div className="bg-white dark:bg-slate-800 p-4 rounded-lg shadow-sm border">
            <div className="flex flex-col sm:flex-row gap-4">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="all">All Statuses</option>
                <option value="open">Open</option>
                <option value="in_progress">In Progress</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="all">All Priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          {/* Tickets List */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Ticket
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      User
                    </th>
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
                <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredTickets.map((ticket) => (
                    <tr key={ticket._id} className="hover:bg-gray-50 dark:bg-slate-700">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-start space-x-3">
                          <span className="text-lg">{getCategoryIcon(ticket.category)}</span>
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                              {ticket.subject}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                              {ticket.category.replace('_', ' ')}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            {ticket.user_name || 'Unknown User'}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">{ticket.user_email}</div>
                        </div>
                      </td>
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
                            onClick={() => setSelectedTicket(ticket)}
                            className="text-wedding-rose hover:text-wedding-rose/80"
                          >
                            Respond
                          </button>
                          {ticket.status !== 'resolved' && (
                            <button
                              onClick={() => updateTicketStatus(ticket._id, 'resolved')}
                              className="text-green-600 dark:text-green-300 hover:text-green-900"
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
          </div>

          {filteredTickets.length === 0 && (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              No tickets found matching your criteria.
            </div>
          )}
        </div>
      )}

      {/* Support Metrics Tab */}
      {activeTab === 'metrics' && metrics && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-wedding-navy">Support Performance</h2>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm border">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Tickets</h3>
              <p className="text-3xl font-bold text-wedding-navy">{metrics.total_tickets}</p>
            </div>
            <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm border">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Open Tickets</h3>
              <p className="text-3xl font-bold text-blue-600">{metrics.open_tickets}</p>
            </div>
            <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm border">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Resolved Today</h3>
              <p className="text-3xl font-bold text-green-600 dark:text-green-300">{metrics.resolved_today}</p>
            </div>
            <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm border">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg Response Time</h3>
              <p className="text-3xl font-bold text-yellow-600">{metrics.avg_response_time}h</p>
            </div>
            <div className="bg-white dark:bg-slate-800 p-6 rounded-lg shadow-sm border">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Satisfaction Score</h3>
              <p className="text-3xl font-bold text-purple-600">{metrics.satisfaction_score}/5</p>
            </div>
          </div>
        </div>
      )}

      {/* Knowledge Base Tab */}
      {activeTab === 'knowledge_base' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-wedding-navy">Knowledge Base</h2>
            <button className="px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80">
              Create Article
            </button>
          </div>
          <div className="bg-white dark:bg-slate-800 p-8 rounded-lg shadow-sm border text-center">
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">Knowledge Base Coming Soon</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Create and manage help articles, FAQs, and documentation for your users.
            </p>
          </div>
        </div>
      )}

      {/* Response Modal */}
      {selectedTicket && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-semibold text-wedding-navy mb-4">
              Respond to Ticket: {selectedTicket.subject}
            </h2>
            <div className="mb-4 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
              <div className="flex justify-between items-start mb-2">
                <span className="font-medium">{selectedTicket.user_name}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {formatDate(selectedTicket.created_at)}
                </span>
              </div>
              <p className="text-gray-700 dark:text-gray-300">{selectedTicket.message}</p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Your Response</label>
              <textarea
                value={responseMessage}
                onChange={(e) => setResponseMessage(e.target.value)}
                placeholder="Enter your response..."
                rows={6}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setSelectedTicket(null);
                  setResponseMessage('');
                }}
                className="px-4 py-2 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg hover:bg-gray-50 dark:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={sendResponse}
                className="px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80"
              >
                Send Response
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
