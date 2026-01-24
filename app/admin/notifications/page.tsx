'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';

interface NotificationTemplate {
  _id: string;
  name: string;
  subject: string;
  content: string;
  type: 'email' | 'sms';
  category?: 'system_update' | 'maintenance' | 'security' | 'marketing' | 'feature_announcement' | 'general';
  variables?: string[];
  is_active?: boolean;
  created_at: string;
  updated_at: string;
  created_by?: string;
}

interface SentNotification {
  _id: string;
  title: string;  // Backend uses "title" not "subject"
  message?: string;
  total_recipients: number;  // Backend uses "total_recipients" not "recipients_count"
  sent_at: string;
  status: 'active' | 'sent' | 'delivered' | 'failed';  // Backend uses "status" not "delivery_status"
  delivery_summary?: {
    attempted: number;
    sent: number;
    failed: number;
    delivered_count?: number;
    opened_count?: number;
    clicked_count?: number;
  };
}

// Planner notification (received notifications like form submissions, RSVPs)
interface PlannerNotification {
  _id: string;
  type: 'form_submission' | 'rsvp_update' | 'guest_message' | 'payment_received' | 'payment_failed' | 'contract_signed' | 'vendor_response' | 'system' | 'reminder';
  title: string;
  message: string;
  wedding_id?: string;
  wedding_name?: string;
  is_read: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
  source?: 'platform' | 'activity';
}

export default function NotificationsPage() {
  const { apiRequest, userProfile } = useAdmin();
  const [activeTab, setActiveTab] = useState<'send' | 'templates' | 'history'>('send');
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [sentNotifications, setSentNotifications] = useState<SentNotification[]>([]);
  const [plannerNotifications, setPlannerNotifications] = useState<PlannerNotification[]>([]);
  const [loading, setLoading] = useState(true);

  // Check if user is root admin
  const isRootAdmin = userProfile?.is_root_admin === true;
  // Send notification form
  const [useTemplate, setUseTemplate] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [customSubject, setCustomSubject] = useState('');
  const [customContent, setCustomContent] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('all_users');
  const [sending, setSending] = useState(false);
  // Template creation modal
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateSubject, setTemplateSubject] = useState('');
  const [templateContent, setTemplateContent] = useState('');
  const [templateType, setTemplateType] = useState<'email' | 'sms'>('email');
  const [templateCategory, setTemplateCategory] = useState<'system_update' | 'maintenance' | 'security' | 'marketing' | 'feature_announcement'>('system_update');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);

      if (isRootAdmin) {
        // Admin view: fetch templates and sent notifications
        try {
          const templatesResponse = await apiRequest<{ templates: NotificationTemplate[] }>('/admin/notification-templates', 'GET');
          setTemplates(templatesResponse?.templates ?? []);
        } catch (error) {
          console.warn('Notification templates endpoint not available, using empty array');
          setTemplates([]);
        }

        try {
          const historyResponse = await apiRequest<{ notifications: SentNotification[] }>('/admin/notifications', 'GET');
          setSentNotifications(historyResponse?.notifications ?? []);
        } catch (error) {
          console.warn('Notification history endpoint not available, using empty array');
          setSentNotifications([]);
        }
      } else {
        // Planner view: fetch platform announcements + activity notifications
        try {
          // Platform announcements (from root admin)
          const platformResponse = await apiRequest<{ notifications: PlannerNotification[] }>('/admin/user/notifications', 'GET');

          // Activity notifications (form submissions, RSVPs, etc.) - will be implemented
          let activityNotifications: PlannerNotification[] = [];
          try {
            const activityResponse = await apiRequest<{ notifications: PlannerNotification[] }>('/admin/planner/activity-notifications', 'GET');
            activityNotifications = activityResponse?.notifications ?? [];
          } catch {
            // Activity notifications endpoint not yet implemented - that's okay
          }

          // Combine and sort by date (newest first)
          const combined = [
            ...(platformResponse?.notifications ?? []).map(n => ({ ...n, source: 'platform' as const })),
            ...activityNotifications.map(n => ({ ...n, source: 'activity' as const }))
          ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

          setPlannerNotifications(combined);
        } catch (error) {
          console.warn('Error fetching notifications:', error);
          setPlannerNotifications([]);
        }
      }
    } catch (error) {
      console.error('Error fetching notification data:', error);
      setTemplates([]);
      setSentNotifications([]);
      setPlannerNotifications([]);
    } finally {
      setLoading(false);
    }
  }, [apiRequest, isRootAdmin]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Dispatch custom event to update bell count in TopHeader
  const dispatchNotificationUpdate = () => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('notifications-updated'));
    }
  };

  // Mark a single activity notification as read
  const markNotificationAsRead = async (notificationId: string, source?: 'platform' | 'activity') => {
    try {
      if (source === 'activity') {
        await apiRequest(`/admin/planner/activity-notifications/${notificationId}/read`, 'PUT');
      } else {
        await apiRequest(`/admin/user/notifications/${notificationId}/read`, 'PUT');
      }

      // Update local state
      setPlannerNotifications(prev =>
        prev.map(n => n._id === notificationId ? { ...n, is_read: true } : n)
      );

      // Dispatch event to update bell
      dispatchNotificationUpdate();
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  // Mark all notifications as read
  const markAllAsRead = async () => {
    try {
      // Mark both platform and activity notifications as read
      await Promise.allSettled([
        apiRequest('/admin/user/notifications/read-all', 'PUT'),
        apiRequest('/admin/planner/activity-notifications/read-all', 'PUT')
      ]);

      // Update local state
      setPlannerNotifications(prev => prev.map(n => ({ ...n, is_read: true })));

      // Dispatch event to update bell
      dispatchNotificationUpdate();
    } catch (error) {
      console.error('Failed to mark all as read:', error);
    }
  };

  const handleCreateTemplate = async () => {
    if (!templateName || !templateSubject || !templateContent) {
      alert('Please fill in all template fields');
      return;
    }

    try {
      // Call backend API to create template
      const response = await apiRequest('/admin/notification-templates', 'POST', {
        name: templateName,
        subject: templateSubject,
        content: templateContent,
        type: templateType,
        category: templateCategory,
        variables: [], // Can be extracted from content in future
        is_active: true
      });

      if (response) {
        setShowTemplateModal(false);
        // Reset form
        setTemplateName('');
        setTemplateSubject('');
        setTemplateContent('');
        setTemplateType('email');
        setTemplateCategory('system_update');

        // Refresh templates list
        await fetchData();

        alert('Template created successfully!');
      }
    } catch (error) {
      console.error('Error creating template:', error);
      alert('Failed to create template. Please try again.');
    }
  };

  const sendNotification = async () => {
    if (!customSubject || !customContent) {
      alert('Please fill in both subject and content');
      return;
    }

    setSending(true);
    try {
      // Map frontend filter to backend target_audience
      let targetAudience = 'all';
      if (recipientFilter === 'wedding_planners') {
        targetAudience = 'wedding_planners';
      }
      // Note: backend doesn't currently support trial/premium filtering,
      // so they map to 'all' for now

      // Step 1: Create notification
      const createResponse = await apiRequest<{id: string}>('/admin/notifications', 'POST', {
        title: customSubject,
        message: customContent,
        type: 'info',
        target_audience: targetAudience,
        is_dismissible: true,
        priority: 'medium'
      });

      if (!createResponse || !createResponse.id) {
        throw new Error('Failed to create notification');
      }

      // Step 2: Send the notification
      const sendResponse = await apiRequest(`/admin/notifications/${createResponse.id}/send`, 'POST', {});

      if (sendResponse) {
        alert(`Notification sent successfully! Delivered to ${sendResponse.sent || 0} users.`);
        setCustomSubject('');
        setCustomContent('');
        setRecipientFilter('all_users');
        setUseTemplate(false);
        setSelectedTemplateId('');

        // Refresh history
        fetchData();
      }

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

  // ============================================
  // PLANNER VIEW - Show received notifications
  // ============================================
  if (!isRootAdmin) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Notifications"
          description="Form submissions, RSVP updates, and activity alerts"
        >
          {plannerNotifications.some(n => !n.is_read) && (
            <button
              onClick={markAllAsRead}
              className="px-4 py-2 text-sm font-medium text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-200 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg transition-colors"
            >
              Mark all as read
            </button>
          )}
        </PageHeader>

        {/* Notifications List */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
          {plannerNotifications.length > 0 ? (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {plannerNotifications.map((notification) => (
                <div
                  key={notification._id}
                  onClick={() => !notification.is_read && markNotificationAsRead(notification._id, notification.source)}
                  className={`p-4 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors ${
                    !notification.is_read ? 'bg-blue-50 dark:bg-blue-900/20 cursor-pointer' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${
                          notification.type === 'form_submission' ? 'bg-green-500' :
                          notification.type === 'rsvp_update' ? 'bg-blue-500' :
                          notification.type === 'guest_message' ? 'bg-purple-500' :
                          notification.type === 'payment_received' ? 'bg-emerald-500' :
                          notification.type === 'payment_failed' ? 'bg-red-500' :
                          notification.type === 'contract_signed' ? 'bg-indigo-500' :
                          notification.type === 'vendor_response' ? 'bg-amber-500' :
                          notification.type === 'reminder' ? 'bg-orange-500' :
                          'bg-gray-500'
                        }`} />
                        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {notification.title}
                        </h3>
                        {!notification.is_read && (
                          <span className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
                            New
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        {notification.message}
                      </p>
                      <div className="mt-2 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
                        <span>{formatDate(notification.created_at)}</span>
                        {notification.wedding_name && (
                          <span className="text-indigo-600 dark:text-indigo-400">
                            {notification.wedding_name}
                          </span>
                        )}
                        <span className="capitalize px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">
                          {notification.type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <div className="text-gray-400 dark:text-gray-500 text-5xl mb-4">🔔</div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Notifications Yet</h3>
              <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto">
                You'll receive notifications here when guests submit forms, update their RSVPs,
                or when there are important updates for your weddings.
              </p>
            </div>
          )}
        </div>

        {/* Notification Types Legend */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Notification Types</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Form Submissions</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">RSVP Updates</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-emerald-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Payments Received</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Failed Payments</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-indigo-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Contracts Signed</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Vendor Responses</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-purple-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Guest Messages</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-orange-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Reminders</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ============================================
  // ROOT ADMIN VIEW - Platform notifications
  // ============================================
  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Notifications"
        description="Send announcements and updates to all users"
      />

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
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
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border p-6">
          <h2 className="text-xl font-semibold text-wedding-navy mb-4">Send New Notification</h2>
          <div className="space-y-4">
            {/* Template Toggle */}
            <div className="flex items-center gap-3 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
              <input
                type="checkbox"
                id="use-template"
                checked={useTemplate}
                onChange={(e) => {
                  setUseTemplate(e.target.checked);
                  if (e.target.checked && templates.length > 0) {
                    const template = templates[0];
                    setSelectedTemplateId(template._id);
                    setCustomSubject(template.subject);
                    setCustomContent(template.content);
                  } else {
                    setSelectedTemplateId('');
                    setCustomSubject('');
                    setCustomContent('');
                  }
                }}
                className="h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded"
              />
              <label htmlFor="use-template" className="text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 cursor-pointer">
                Use a template
              </label>
            </div>

            {/* Template Selection */}
            {useTemplate && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Select Template *</label>
                <select
                  value={selectedTemplateId}
                  onChange={(e) => {
                    setSelectedTemplateId(e.target.value);
                    const template = templates.find(t => t._id === e.target.value);
                    if (template) {
                      setCustomSubject(template.subject);
                      setCustomContent(template.content);
                    }
                  }}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="">-- Select a template --</option>
                  {templates.filter(t => t.is_active !== false).map(template => (
                    <option key={template._id} value={template._id}>
                      {template.name} ({template.type.toUpperCase()}) - {template.subject}
                    </option>
                  ))}
                </select>
                {templates.length === 0 && (
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">No templates available. Create one in the Templates tab.</p>
                )}
              </div>
            )}

            {/* Recipients */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Recipients *</label>
              <select
                value={recipientFilter}
                onChange={(e) => setRecipientFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Subject Line *</label>
              <input
                type="text"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                placeholder="Enter email subject..."
                disabled={useTemplate && selectedTemplateId !== ''}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent disabled:bg-gray-100 dark:bg-slate-700 disabled:cursor-not-allowed"
              />
              {useTemplate && selectedTemplateId && (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Subject is loaded from template (read-only)</p>
              )}
            </div>

            {/* Content */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Message Content *</label>
              <textarea
                value={customContent}
                onChange={(e) => setCustomContent(e.target.value)}
                placeholder="Enter your message content..."
                rows={8}
                disabled={useTemplate && selectedTemplateId !== ''}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent disabled:bg-gray-100 dark:bg-slate-700 disabled:cursor-not-allowed"
              />
              {useTemplate && selectedTemplateId && (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Content is loaded from template (read-only)</p>
              )}
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
                <div key={template._id} className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 dark:text-white">{template.name}</h3>
                    <div className="flex gap-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${
                        template.type === 'email'
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      }`}>
                        {template.type?.toUpperCase() || 'EMAIL'}
                      </span>
                      {template.category && (
                        <span className="px-2 py-1 text-xs font-medium rounded bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 dark:bg-gray-700 dark:text-gray-300">
                          {template.category.replace('_', ' ').toUpperCase()}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400 mb-3 font-medium">{template.subject}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-500 line-clamp-2">{template.content}</p>
                  <div className="mt-4 pt-4 border-t dark:border-gray-700 flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 dark:text-gray-400">
                    <span>Created: {new Date(template.created_at).toLocaleDateString()}</span>
                    {template.is_active !== undefined && (
                      <span className={template.is_active ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                        {template.is_active ? '● Active' : '○ Inactive'}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border p-8 text-center">
              <div className="text-gray-400 text-4xl mb-4">📧</div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Templates Yet</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
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
          <h2 className="text-xl font-semibold text-wedding-navy dark:text-white">Notification History</h2>
          {sentNotifications.length > 0 ? (
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border dark:border-gray-700 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-400">Subject</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-400">Recipients</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-400">Sent Date</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-500 dark:text-gray-400 dark:text-gray-400">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sentNotifications.map((notification) => (
                    <tr key={notification._id} className="border-t hover:bg-gray-50 dark:hover:bg-gray-800 dark:border-gray-700">
                      <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100 dark:text-gray-100 font-medium">{notification.title}</td>
                      <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300 dark:text-gray-300">
                        {notification.delivery_summary ?
                          `${notification.delivery_summary.sent}/${notification.total_recipients}` :
                          notification.total_recipients
                        }
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300 dark:text-gray-300">{formatDate(notification.sent_at)}</td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          notification.status === 'sent' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                          notification.status === 'delivered' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                          notification.status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                          'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                        }`}>
                          {notification.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border dark:border-gray-700 p-8 text-center">
              <div className="text-gray-400 dark:text-gray-600 dark:text-gray-400 text-4xl mb-4">📊</div>
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 dark:text-white mb-2">No Notifications Sent Yet</h3>
              <p className="text-gray-600 dark:text-gray-400 dark:text-gray-400 mb-4">
                Once you start sending platform notifications, you'll see delivery statistics,
                open rates, and performance metrics here.
              </p>
              <div className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-400">
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
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <div className="flex justify-between items-center">
                <h2 className="text-2xl font-semibold text-wedding-navy">Create Notification Template</h2>
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className="text-gray-400 hover:text-gray-600 dark:text-gray-400 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Template Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Template Name *</label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g., System Maintenance Notice"
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Delivery Method */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Delivery Method *</label>
                <select
                  value={templateType}
                  onChange={(e) => setTemplateType(e.target.value as any)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                >
                  <option value="email">Email</option>
                  <option value="sms">SMS</option>
                </select>
              </div>

              {/* Template Category */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Category *</label>
                <select
                  value={templateCategory}
                  onChange={(e) => setTemplateCategory(e.target.value as any)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">
                  {templateType === 'email' ? 'Email Subject' : 'SMS Preview Text'} *
                </label>
                <input
                  type="text"
                  value={templateSubject}
                  onChange={(e) => setTemplateSubject(e.target.value)}
                  placeholder={templateType === 'email' ? 'Enter email subject line...' : 'Enter SMS preview text...'}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Content */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Message Content *</label>
                <textarea
                  value={templateContent}
                  onChange={(e) => setTemplateContent(e.target.value)}
                  placeholder="Enter your template message..."
                  rows={8}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className="px-6 py-2 border border-gray-300 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:bg-slate-700"
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
