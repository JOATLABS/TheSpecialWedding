'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
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
  sent_at?: string;  // Only set when notification is actually sent
  created_at: string;  // Always set when notification is created
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
// Also includes root admin notification types (support_ticket, system_config, sales_contact)
// And support_ticket_response for when root admin responds to planner tickets
interface PlannerNotification {
  _id: string;
  type: 'form_submission' | 'rsvp_update' | 'guest_message' | 'payment_received' | 'payment_failed' | 'contract_signed' | 'vendor_response' | 'system' | 'reminder' | 'support_ticket' | 'system_config' | 'sales_contact' | 'support_ticket_response';
  title: string;
  message: string;
  wedding_id?: string;
  wedding_name?: string;
  is_read: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
  source?: 'platform' | 'activity';
}

const surfaceClass =
  'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800/95';

const mutedSurfaceClass =
  'rounded-xl bg-slate-50 dark:bg-slate-700/50';

const inputClass =
  'w-full rounded-xl border border-slate-300 bg-white px-4 py-2 text-slate-900 transition-colors focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/20 disabled:cursor-not-allowed disabled:bg-slate-100 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:disabled:bg-slate-800';

const labelClass = 'mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300';

const secondaryButtonClass =
  'rounded-lg border border-slate-300 bg-white px-6 py-2 text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600';

export default function NotificationsPage() {
  const { apiRequest, userProfile } = useAdmin();
  const searchParams = useSearchParams();
  const tabFromUrl = searchParams.get('tab');

  // Initialize tab from URL query param, default to 'send' for root admin
  const getInitialTab = (): 'send' | 'templates' | 'history' => {
    if (tabFromUrl === 'history') return 'history';
    if (tabFromUrl === 'templates') return 'templates';
    return 'send';
  };

  const [activeTab, setActiveTab] = useState<'send' | 'templates' | 'history'>(getInitialTab);
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [sentNotifications, setSentNotifications] = useState<SentNotification[]>([]);
  const [plannerNotifications, setPlannerNotifications] = useState<PlannerNotification[]>([]);
  const [loading, setLoading] = useState(true);

  // Check if user is root admin
  const isRootAdmin = userProfile?.is_root_admin === true;

  // Update tab when URL query param changes (e.g., clicking bell icon with ?tab=history)
  useEffect(() => {
    if (tabFromUrl) {
      if (tabFromUrl === 'history') setActiveTab('history');
      else if (tabFromUrl === 'templates') setActiveTab('templates');
      else if (tabFromUrl === 'send') setActiveTab('send');
    }
  }, [tabFromUrl]);
  // Send notification form
  const [useTemplate, setUseTemplate] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [customSubject, setCustomSubject] = useState('');
  const [customContent, setCustomContent] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('all');
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

  // Dispatch custom event to update bell count in TopHeader
  const dispatchNotificationUpdate = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('notifications-updated'));
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Dispatch update event on mount to ensure bell badge count is current
    dispatchNotificationUpdate();
  }, [fetchData, dispatchNotificationUpdate]);

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
      // recipientFilter directly maps to backend target_audience: 'all', 'wedding_planners', 'vendors'
      // Step 1: Create notification
      const createResponse = await apiRequest<{id: string}>('/admin/notifications', 'POST', {
        title: customSubject,
        message: customContent,
        type: 'info',
        target_audience: recipientFilter,
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
        setRecipientFilter('all');
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
        <div className={surfaceClass}>
          {plannerNotifications.length > 0 ? (
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {plannerNotifications.map((notification) => (
                <div
                  key={notification._id}
                  onClick={() => !notification.is_read && markNotificationAsRead(notification._id, notification.source)}
                  className={`p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-700 ${
                    !notification.is_read ? 'cursor-pointer bg-blue-50/80 dark:bg-blue-900/20' : ''
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
                          notification.type === 'support_ticket_response' ? 'bg-teal-500' :
                          'bg-gray-500'
                        }`} />
                        <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100">
                          {notification.title}
                        </h3>
                        {!notification.is_read && (
                          <span className="px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
                            New
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                        {notification.message}
                      </p>
                      <div className="mt-2 flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                        <span>{formatDate(notification.created_at)}</span>
                        {notification.wedding_name && (
                          <span className="text-indigo-600 dark:text-indigo-400">
                            {notification.wedding_name}
                          </span>
                        )}
                        <span className="rounded bg-slate-100 px-2 py-0.5 capitalize dark:bg-slate-700">
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
              <div className="mb-4 text-5xl text-slate-400 dark:text-slate-500">🔔</div>
              <h3 className="mb-2 text-lg font-medium text-slate-900 dark:text-slate-100">No Notifications Yet</h3>
              <p className="mx-auto max-w-md text-slate-600 dark:text-slate-400">
                You'll receive notifications here when guests submit forms, update their RSVPs,
                or when there are important updates for your weddings.
              </p>
            </div>
          )}
        </div>

        {/* Notification Types Legend */}
        <div className={`${surfaceClass} p-4`}>
          <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">Notification Types</h3>
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
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-teal-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Support Responses</span>
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
      <div className="border-b border-slate-200 dark:border-slate-700">
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
                  : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:border-slate-600 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Send Notification Tab */}
      {activeTab === 'send' && (
        <div className={`${surfaceClass} p-6`}>
          <h2 className="mb-4 text-xl font-semibold text-wedding-navy dark:text-white">Send New Notification</h2>
          <div className="space-y-4">
            {/* Template Toggle */}
            <div className={`flex items-center gap-3 p-4 ${mutedSurfaceClass}`}>
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
              <label htmlFor="use-template" className="cursor-pointer text-sm font-medium text-slate-700 dark:text-slate-300">
                Use a template
              </label>
            </div>

            {/* Template Selection */}
            {useTemplate && (
              <div>
                <label className={labelClass}>Select Template *</label>
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
                  className={inputClass}
                >
                  <option value="">-- Select a template --</option>
                  {templates.filter(t => t.is_active !== false).map(template => (
                    <option key={template._id} value={template._id}>
                      {template.name} ({template.type.toUpperCase()}) - {template.subject}
                    </option>
                  ))}
                </select>
                {templates.length === 0 && (
                  <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No templates available. Create one in the Templates tab.</p>
                )}
              </div>
            )}

            {/* Recipients */}
            <div>
              <label className={labelClass}>Recipients *</label>
              <select
                value={recipientFilter}
                onChange={(e) => setRecipientFilter(e.target.value)}
                className={inputClass}
              >
                <option value="all">All Users</option>
                <option value="wedding_planners">Wedding Planners</option>
                <option value="vendors">Vendors</option>
              </select>
            </div>

            {/* Subject */}
            <div>
              <label className={labelClass}>Subject Line *</label>
              <input
                type="text"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                placeholder="Enter email subject..."
                disabled={useTemplate && selectedTemplateId !== ''}
                className={inputClass}
              />
              {useTemplate && selectedTemplateId && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Subject is loaded from template (read-only)</p>
              )}
            </div>

            {/* Content */}
            <div>
              <label className={labelClass}>Message Content *</label>
              <textarea
                value={customContent}
                onChange={(e) => setCustomContent(e.target.value)}
                placeholder="Enter your message content..."
                rows={8}
                disabled={useTemplate && selectedTemplateId !== ''}
                className={inputClass}
              />
              {useTemplate && selectedTemplateId && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Content is loaded from template (read-only)</p>
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
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-white">Notification Templates</h2>
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
                <div key={template._id} className={`${surfaceClass} rounded-xl p-6 transition-shadow hover:shadow-md`}>
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-lg font-medium text-slate-900 dark:text-white">{template.name}</h3>
                    <div className="flex gap-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded ${
                        template.type === 'email'
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                          : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      }`}>
                        {template.type?.toUpperCase() || 'EMAIL'}
                      </span>
                      {template.category && (
                        <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                          {template.category.replace('_', ' ').toUpperCase()}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="mb-3 text-sm font-medium text-slate-600 dark:text-slate-400">{template.subject}</p>
                  <p className="line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{template.content}</p>
                  <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    <span>Created: {formatDate(template.created_at)}</span>
                    {template.is_active !== undefined && (
                      <span className={template.is_active ? 'text-green-600 dark:text-green-400' : 'text-slate-400'}>
                        {template.is_active ? '● Active' : '○ Inactive'}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={`${surfaceClass} p-8 text-center`}>
              <div className="mb-4 text-4xl text-slate-400">📧</div>
              <h3 className="mb-2 text-lg font-medium text-slate-900 dark:text-slate-100">No Templates Yet</h3>
              <p className="mb-4 text-slate-600 dark:text-slate-400">
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
            <div className={`${surfaceClass} overflow-hidden`}>
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-medium text-slate-500 dark:text-slate-400">Subject</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-slate-500 dark:text-slate-400">Recipients</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-slate-500 dark:text-slate-400">Date</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-slate-500 dark:text-slate-400">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sentNotifications.map((notification) => (
                    <tr key={notification._id} className="border-t border-slate-200 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
                      <td className="px-6 py-4 text-sm font-medium text-slate-900 dark:text-slate-100">{notification.title}</td>
                      <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                        {notification.delivery_summary ?
                          `${notification.delivery_summary.sent}/${notification.total_recipients}` :
                          notification.total_recipients
                        }
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-700 dark:text-slate-300">
                        {notification.sent_at ? formatDate(notification.sent_at) : formatDate(notification.created_at)}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          notification.status === 'sent' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                          notification.status === 'delivered' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                          notification.status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                          notification.status === 'active' ? 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200' :
                          'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                        }`}>
                          {notification.status === 'active' ? 'DRAFT' : notification.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className={`${surfaceClass} p-8 text-center`}>
              <div className="mb-4 text-4xl text-slate-400 dark:text-slate-500">📊</div>
              <h3 className="mb-2 text-lg font-medium text-slate-900 dark:text-slate-100">No Notifications Sent Yet</h3>
              <p className="mb-4 text-slate-600 dark:text-slate-400">
                Once you start sending platform notifications, you'll see delivery statistics,
                open rates, and performance metrics here.
              </p>
              <div className="text-sm text-slate-500 dark:text-slate-400">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800">
            <div className="border-b border-slate-200 p-6 dark:border-slate-700">
              <div className="flex justify-between items-center">
                <h2 className="text-2xl font-semibold text-wedding-navy dark:text-white">Create Notification Template</h2>
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className="text-2xl text-slate-400 transition-colors hover:text-slate-600 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Template Name */}
              <div>
                <label className={labelClass}>Template Name *</label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g., System Maintenance Notice"
                  className={inputClass}
                />
              </div>

              {/* Delivery Method */}
              <div>
                <label className={labelClass}>Delivery Method *</label>
                <select
                  value={templateType}
                  onChange={(e) => setTemplateType(e.target.value as any)}
                  className={inputClass}
                >
                  <option value="email">Email</option>
                  <option value="sms">SMS</option>
                </select>
              </div>

              {/* Template Category */}
              <div>
                <label className={labelClass}>Category *</label>
                <select
                  value={templateCategory}
                  onChange={(e) => setTemplateCategory(e.target.value as any)}
                  className={inputClass}
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
                <label className={labelClass}>
                  {templateType === 'email' ? 'Email Subject' : 'SMS Preview Text'} *
                </label>
                <input
                  type="text"
                  value={templateSubject}
                  onChange={(e) => setTemplateSubject(e.target.value)}
                  placeholder={templateType === 'email' ? 'Enter email subject line...' : 'Enter SMS preview text...'}
                  className={inputClass}
                />
              </div>

              {/* Content */}
              <div>
                <label className={labelClass}>Message Content *</label>
                <textarea
                  value={templateContent}
                  onChange={(e) => setTemplateContent(e.target.value)}
                  placeholder="Enter your template message..."
                  rows={8}
                  className={inputClass}
                />
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowTemplateModal(false)}
                  className={secondaryButtonClass}
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
