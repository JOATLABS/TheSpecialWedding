'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';

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
  // Template creation modal
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateSubject, setTemplateSubject] = useState('');
  const [templateContent, setTemplateContent] = useState('');
  const [templateType, setTemplateType] = useState<'system_update' | 'maintenance' | 'security' | 'marketing' | 'feature_announcement'>('system_update');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      // Try to fetch from actual API endpoints, fall back to empty arrays
      try {
        // These endpoints would need to be created in the backend
        const templatesResponse = await apiRequest<{ templates: NotificationTemplate[] }>('/api/admin/notification-templates', 'GET');
        setTemplates(templatesResponse?.templates ?? []);
      } catch (error) {
        console.warn('Notification templates endpoint not available, using empty array');
        setTemplates([]);
      }

      try {
        const historyResponse = await apiRequest<{ notifications: SentNotification[] }>('/api/admin/notifications/history', 'GET');
        setSentNotifications(historyResponse?.notifications ?? []);
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
  }, [apiRequest]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);


  const handleCreateTemplate = async () => {
    if (!templateName || !templateSubject || !templateContent) {
      alert('Please fill in all template fields');
      return;
    }

    try {
      // For now, just add to local state - backend integration in Option B
      const newTemplate: NotificationTemplate = {
        _id: `temp_${Date.now()}`,
        name: templateName,
        subject: templateSubject,
        content: templateContent,
        type: templateType,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      setTemplates([...templates, newTemplate]);
      setShowTemplateModal(false);
      // Reset form
      setTemplateName('');
      setTemplateSubject('');
      setTemplateContent('');
      setTemplateType('system_update');

      alert('Template created successfully! (Note: This will be saved to database in backend integration)');
    } catch (error) {
      console.error('Error creating template:', error);
      alert('Failed to create template');
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
      const usersResponse = await apiRequest<any[]>('/api/admin/users', 'GET');
      const allUsers = usersResponse ?? [];
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

      // Send notification (this endpoint would need to be created)
      const response = await apiRequest('/api/admin/notifications/send', 'POST', {
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
        <div className="text-lg">Loading notifications...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-heading text-wedding-rose">Platform Notifications</h1>
        <p className="text-gray-600">Send announcements and updates to all users</p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { key: 'send', label: 'Send Notification' },
            { key: 'templates', label: 'Templates' },
            { key: 'history', label: 'History' }
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

      {/* Send Notification Tab */}
      {activeTab === 'send' && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-xl font-semibold text-wedding-navy mb-4">Send New Notification</h2>
          <div className="space-y-4">
            {/* Recipients */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Recipients</label>
              <select
                value={recipientFilter}
                onChange={(e) => setRecipientFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
              <label className="block text-sm font-medium text-gray-700 mb-2">Subject Line *</label>
              <input
                type="text"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                placeholder="Enter email subject..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            {/* Content */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Message Content *</label>
              <textarea
                value={customContent}
                onChange={(e) => setCustomContent(e.target.value)}
                placeholder="Enter your message content..."
                rows={8}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
              />
            </div>

            {/* Send Button */}
            <div className="flex justify-end">
              <button
                onClick={sendNotification}
                disabled={sending || !customSubject || !customContent}
                className="px-6 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80 disabled:opacity-50"
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
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-wedding-navy">Notification Templates</h2>
            <button
              onClick={() => setShowTemplateModal(true)}
              className="px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80"
            >
              Create Template
            </button>
          </div>
          {templates.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {templates.map((template) => (
                <div key={template._id} className="bg-white rounded-lg shadow-sm border p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">{template.name}</h3>
                  <p className="text-sm text-gray-600 mb-4">{template.subject}</p>
                  <p className="text-sm text-gray-500">{template.content.substring(0, 100)}...</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
              <div className="text-gray-400 text-4xl mb-4">📧</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Templates Yet</h3>
              <p className="text-gray-600 mb-4">
                Create reusable notification templates for common announcements like maintenance,
                feature updates, or security notices.
              </p>
              <button
                onClick={() => setShowTemplateModal(true)}
                className="px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80"
              >
                Create Your First Template
              </button>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-wedding-navy">Notification History</h2>
          {sentNotifications.length > 0 ? (
            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500">Subject</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500">Recipients</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500">Sent Date</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sentNotifications.map((notification) => (
                    <tr key={notification._id} className="border-t">
                      <td className="px-6 py-4 text-sm">{notification.subject}</td>
                      <td className="px-6 py-4 text-sm">{notification.recipients_count}</td>
                      <td className="px-6 py-4 text-sm">{formatDate(notification.sent_at)}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">
                          {notification.delivery_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
              <div className="text-gray-400 text-4xl mb-4">📊</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Notifications Sent Yet</h3>
              <p className="text-gray-600 mb-4">
                Once you start sending platform notifications, you’ll see delivery statistics,
                open rates, and performance metrics here.
              </p>
              <div className="text-sm text-gray-500">
                <p>• View delivery status and recipient counts</p>
                <p>• Track open and click rates</p>
                <p>• Monitor notification performance over time</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Template Creation Modal */}
      {showTemplateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <div className="flex justify-between items-center">
                <h2 className="text-2xl font-semibold text-wedding-navy">Create Notification Template</h2>
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Template Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Template Name *</label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g., System Maintenance Notice"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Template Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Template Type *</label>
                <select
                  value={templateType}
                  onChange={(e) => setTemplateType(e.target.value as any)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="system_update">System Update</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="security">Security Notice</option>
                  <option value="marketing">Marketing</option>
                  <option value="feature_announcement">Feature Announcement</option>
                </select>
              </div>

              {/* Subject */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Email Subject *</label>
                <input
                  type="text"
                  value={templateSubject}
                  onChange={(e) => setTemplateSubject(e.target.value)}
                  placeholder="Enter email subject line..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Content */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Message Content *</label>
                <textarea
                  value={templateContent}
                  onChange={(e) => setTemplateContent(e.target.value)}
                  placeholder="Enter your template message..."
                  rows={8}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateTemplate}
                  disabled={!templateName || !templateSubject || !templateContent}
                  className="px-6 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/80 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create Template
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}