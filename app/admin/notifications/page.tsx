'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

interface NotificationTemplate {
  _id: string;
  name: string;
  subject: string;
  content: string;
  type: 'system_update' | 'maintenance' | 'security' | 'marketing' | 'feature_announcement';
  created_at: string;
  updated_at: string;
}

interface SentNotification {
  _id: string;
  template_name: string;
  subject: string;
  recipients_count: number;
  sent_at: string;
  delivery_status: 'sent' | 'delivered' | 'failed';
  open_rate?: number;
  click_rate?: number;
}

export default function NotificationsPage() {
  const { apiRequest } = useAdmin();
  const [activeTab, setActiveTab] = useState<'send' | 'templates' | 'history'>('send');
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [sentNotifications, setSentNotifications] = useState<SentNotification[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Send notification form
  const [customSubject, setCustomSubject] = useState('');
  const [customContent, setCustomContent] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('all_users');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Try to fetch from actual API endpoints, fall back to empty arrays
      try {
        // These endpoints exist in the backend at /admin/notification-templates
        const templatesResponse = await apiRequest('/admin/notification-templates', 'GET');
        setTemplates(templatesResponse.templates || []);
      } catch (error) {
        console.warn('Notification templates endpoint not available, using empty array');
        setTemplates([]);
      }

      try {
        // Backend endpoint is /admin/notifications with GET method
        const historyResponse = await apiRequest('/admin/notifications', 'GET');

        // Transform notifications to match expected format
        const transformedNotifications = (historyResponse.notifications || []).map((n: any) => {
          return {
            ...n,
            subject: n.title || 'Notification',
            recipients_count: n.total_recipients || 0,
            sent_at: n.created_at || new Date().toISOString(),
            delivery_status: n.status === 'active' ? 'sent' : (n.status || 'sent')
          };
        });

        setSentNotifications(transformedNotifications);
      } catch (error) {
        console.warn('Notification history endpoint not available, using empty array');
        setSentNotifications([]);
      }
      
    } catch (error) {
      console.error('Error fetching notification data:', error);
      setTemplates([]);
      setSentNotifications([]);
    } finally {
      setLoading(false);
    }
  };


  const sendNotification = async () => {
    if (!customSubject || !customContent) {
      alert('Please fill in both subject and content');
      return;
    }

    setSending(true);
    try {
      // First get the users to send to based on filter
      const usersResponse = await apiRequest('/api/admin/users', 'GET');
      const allUsers = usersResponse || [];
      
      let targetUsers = [];
      switch (recipientFilter) {
        case 'all_users':
          targetUsers = allUsers;
          break;
        case 'active_users':
          targetUsers = allUsers.filter((u: any) => u.is_active);
          break;
        case 'wedding_planners':
          targetUsers = allUsers.filter((u: any) => u.is_wedding_planner && u.is_active);
          break;
        case 'trial_users':
          targetUsers = allUsers.filter((u: any) => u.subscription_status === 'trialing');
          break;
        case 'premium_users':
          targetUsers = allUsers.filter((u: any) => u.subscription_status === 'active');
          break;
      }

      // Send notification - backend endpoint is /admin/notifications/send
      const response = await apiRequest('/admin/notifications/send', 'POST', {
        subject: customSubject,
        content: customContent,
        recipient_filter: recipientFilter,
        target_emails: targetUsers.map((u: any) => u.email)
      });

      alert(`Notification queued for ${targetUsers.length} users!`);
      setCustomSubject('');
      setCustomContent('');
      setRecipientFilter('all_users');
      
      // Refresh history
      fetchData();
      
    } catch (error) {
      console.error('Error sending notification:', error);
      alert('Failed to send notification. Note: This feature requires backend implementation.');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-900 dark:text-gray-100">Loading notifications...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-heading text-wedding-rose">Platform Notifications</h1>
        <p className="text-gray-600 dark:text-gray-300">Send announcements and updates to all users</p>
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
            <option value="send">Send Notification</option>
            <option value="templates">Templates</option>
            <option value="history">History</option>
          </select>
        </div>

        {/* Desktop: Tab Navigation */}
        <nav className="hidden sm:flex sm:space-x-8">
          {[
            { key: 'send', label: 'Send Notification' },
            { key: 'templates', label: 'Templates' },
            { key: 'history', label: 'History' }
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

      {/* Send Notification Tab */}
      {activeTab === 'send' && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
          <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">Send New Notification</h2>
          
          <div className="space-y-4">
            {/* Recipients */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Recipients</label>
              <select
                value={recipientFilter}
                onChange={(e) => setRecipientFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              >
                <option value="all_users">All Users</option>
                <option value="active_users">Active Users Only</option>
                <option value="wedding_planners">Wedding Planners Only</option>
                <option value="trial_users">Trial Users</option>
                <option value="premium_users">Premium Users</option>
              </select>
            </div>

            {/* Subject */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Subject Line *</label>
              <input
                type="text"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                placeholder="Enter email subject..."
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            {/* Content */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Message Content *</label>
              <textarea
                value={customContent}
                onChange={(e) => setCustomContent(e.target.value)}
                placeholder="Enter your message content..."
                rows={8}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            {/* Send Button */}
            <div className="flex justify-end">
              <button
                onClick={sendNotification}
                disabled={sending || !customSubject || !customContent}
                className="px-6 py-2 bg-wedding-rose hover:bg-wedding-rose/80 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {sending ? 'Sending...' : 'Send Notification'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100">Notification Templates</h2>
            <button className="px-4 py-2 bg-wedding-rose hover:bg-wedding-rose/80 text-white rounded-lg transition-colors">
              Create Template
            </button>
          </div>
          
          {templates.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {templates.map((template) => (
                <div key={template._id} className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">{template.name}</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">{template.subject}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{template.content.substring(0, 100)}...</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
              <div className="text-gray-400 text-4xl mb-4">📧</div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Templates Yet</h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                Create reusable notification templates for common announcements like maintenance,
                feature updates, or security notices.
              </p>
              <button className="px-4 py-2 bg-wedding-rose hover:bg-wedding-rose/80 text-white rounded-lg transition-colors">
                Create Your First Template
              </button>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100">Notification History</h2>

          {sentNotifications.length > 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* Mobile: Card View */}
              <div className="sm:hidden space-y-4 p-4">
                {sentNotifications.map((notification) => (
                  <div key={notification._id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-2">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{notification.subject}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">{notification.recipients_count} recipients</div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">{new Date(notification.sent_at).toLocaleDateString()}</div>
                    <div>
                      <span className="bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 px-2 py-1 rounded text-xs">
                        {notification.delivery_status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop: Table View */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Subject</th>
                      <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Recipients</th>
                      <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Sent Date</th>
                      <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {sentNotifications.map((notification) => (
                      <tr key={notification._id}>
                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">{notification.subject}</td>
                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">{notification.recipients_count}</td>
                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">{new Date(notification.sent_at).toLocaleDateString()}</td>
                        <td className="px-6 py-4 text-sm">
                          <span className="bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 px-2 py-1 rounded text-xs">
                            {notification.delivery_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
              <div className="text-gray-400 text-4xl mb-4">📊</div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Notifications Sent Yet</h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4">
                Once you start sending platform notifications, you'll see delivery statistics,
                open rates, and performance metrics here.
              </p>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                <p>• View delivery status and recipient counts</p>
                <p>• Track open and click rates</p>
                <p>• Monitor notification performance over time</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}