'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

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

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Try to fetch from actual API endpoints, fall back to empty arrays
      try {
        // These endpoints would need to be created in the backend
        const ticketsResponse = await apiRequest('/api/admin/support/tickets', 'GET');
        setTickets(ticketsResponse.tickets || []);
      } catch (error) {
        console.warn('Support tickets endpoint not available, using empty array');
        setTickets([]);
      }

      try {
        const metricsResponse = await apiRequest('/api/admin/support/metrics', 'GET');
        setMetrics(metricsResponse || {
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
  };


  const updateTicketStatus = async (ticketId: string, newStatus: SupportTicket['status']) => {
    try {
      await apiRequest(`/api/admin/support/tickets/${ticketId}/status`, 'PATCH', {
        status: newStatus
      });

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
      await apiRequest(`/api/admin/support/tickets/${selectedTicket._id}/respond`, 'POST', {
        message: responseMessage
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
      case 'urgent': return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200';
      case 'high': return 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200';
      case 'medium': return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200';
      case 'low': return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200';
      default: return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200';
      case 'in_progress': return 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200';
      case 'resolved': return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200';
      case 'closed': return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200';
      default: return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200';
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
        <div className="text-lg text-gray-900 dark:text-gray-100">Loading support data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-heading text-wedding-rose">Support Center</h1>
        <p className="text-gray-600 dark:text-gray-300">Manage user support tickets and help resources</p>
      </div>

      {/* Navigation - Mobile Friendly */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        {/* Mobile: Dropdown Select */}
        <div className="sm:hidden py-4">
          <select
            value={activeTab}
            onChange={(e) => setActiveTab(e.target.value as any)}
            className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md shadow-sm focus:outline-none focus:ring-wedding-rose focus:border-wedding-rose text-sm font-medium"
          >
            <option value="tickets">Support Tickets</option>
            <option value="metrics">Support Metrics</option>
            <option value="knowledge_base">Knowledge Base</option>
          </select>
        </div>

        {/* Desktop: Tab Navigation */}
        <nav className="hidden sm:flex sm:space-x-8">
          {[
            { key: 'tickets', label: 'Support Tickets' },
            { key: 'metrics', label: 'Support Metrics' },
            { key: 'knowledge_base', label: 'Knowledge Base' }
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
                activeTab === tab.key
                  ? 'border-wedding-rose text-wedding-rose'
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
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <div className="flex flex-col sm:flex-row gap-4">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            {/* Mobile: Card View */}
            <div className="sm:hidden space-y-4 p-4">
              {filteredTickets.map((ticket) => (
                <div key={ticket._id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
                  <div className="flex items-start space-x-3">
                    <span className="text-lg">{getCategoryIcon(ticket.category)}</span>
                    <div className="flex-1">
                      <div className="font-medium text-gray-900 dark:text-gray-100">{ticket.subject}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">{ticket.category.replace('_', ' ')}</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 dark:text-gray-300">User:</span>
                      <div className="text-right">
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{ticket.user_name || 'Unknown User'}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{ticket.user_email}</div>
                      </div>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Priority:</span>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getPriorityColor(ticket.priority)}`}>
                        {ticket.priority}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Status:</span>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(ticket.status)}`}>
                        {ticket.status.replace('_', ' ')}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 dark:text-gray-300">Created:</span>
                      <span className="text-sm text-gray-500 dark:text-gray-400">{new Date(ticket.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="flex space-x-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <button
                      onClick={() => setSelectedTicket(ticket)}
                      className="flex-1 px-3 py-2 text-sm text-wedding-rose border border-wedding-rose rounded-lg hover:bg-wedding-rose hover:text-white transition-colors"
                    >
                      Respond
                    </button>
                    {ticket.status !== 'resolved' && (
                      <button
                        onClick={() => updateTicketStatus(ticket._id, 'resolved')}
                        className="flex-1 px-3 py-2 text-sm text-green-600 dark:text-green-400 border border-green-600 dark:border-green-400 rounded-lg hover:bg-green-600 hover:text-white dark:hover:bg-green-600 transition-colors"
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop: Table View */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
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
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredTickets.map((ticket) => (
                    <tr key={ticket._id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
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
                        {new Date(ticket.created_at).toLocaleDateString()}
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
                              className="text-green-600 dark:text-green-400 hover:text-green-900 dark:hover:text-green-300"
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
          <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100">Support Performance</h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 sm:gap-6">
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Tickets</h3>
              <p className="text-3xl font-bold text-wedding-navy">{metrics.total_tickets}</p>
            </div>
            
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Open Tickets</h3>
              <p className="text-3xl font-bold text-blue-600">{metrics.open_tickets}</p>
            </div>
            
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Resolved Today</h3>
              <p className="text-3xl font-bold text-green-600">{metrics.resolved_today}</p>
            </div>
            
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg Response Time</h3>
              <p className="text-3xl font-bold text-yellow-600">{metrics.avg_response_time}h</p>
            </div>
            
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Satisfaction Score</h3>
              <p className="text-3xl font-bold text-purple-600">{metrics.satisfaction_score}/5</p>
            </div>
          </div>
        </div>
      )}

      {/* Knowledge Base Tab */}
      {activeTab === 'knowledge_base' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100">Knowledge Base</h2>
            <button className="px-4 py-2 bg-wedding-rose hover:bg-wedding-rose/80 text-white rounded-lg transition-colors">
              Create Article
            </button>
          </div>
          
          <div className="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 text-center">
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">Knowledge Base Coming Soon</h3>
            <p className="text-gray-600 dark:text-gray-300">
              Create and manage help articles, FAQs, and documentation for your users.
            </p>
          </div>
        </div>
      )}

      {/* Response Modal */}
      {selectedTicket && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">
              Respond to Ticket: {selectedTicket.subject}
            </h2>
            
            <div className="mb-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex justify-between items-start mb-2">
                <span className="font-medium">{selectedTicket.user_name}</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {new Date(selectedTicket.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-gray-700 dark:text-gray-300">{selectedTicket.message}</p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Your Response</label>
              <textarea
                value={responseMessage}
                onChange={(e) => setResponseMessage(e.target.value)}
                placeholder="Enter your response..."
                rows={6}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setSelectedTicket(null);
                  setResponseMessage('');
                }}
                className="px-4 py-2 text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600"
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