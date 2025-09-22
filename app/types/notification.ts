// Notification related types

export type NotificationTemplateType = 'system_update' | 'maintenance' | 'security' | 'marketing' | 'feature_announcement';

export interface NotificationTemplate {
  _id: string;
  name: string;
  subject: string;
  content: string;
  type: NotificationTemplateType;
  created_at: string;
  updated_at: string;
}

export interface SentNotification {
  _id: string;
  template_name?: string;
  subject: string;
  recipients_count: number;
  sent_at: string;
  delivery_status: 'sent' | 'delivered' | 'failed';
  open_rate?: number;
  click_rate?: number;
}

export interface RawHistoryNotification {
  _id?: string;
  id?: string;
  title?: string;
  total_recipients?: number;
  created_at?: string;
  status?: string;
  [key: string]: unknown;
}

export interface AdminUserProfile {
  email: string;
  is_active?: boolean;
  is_wedding_planner?: boolean;
  subscription_status?: string; // 'trialing' | 'active' | etc.
  [key: string]: unknown;
}

export type RecipientFilter = 'all_users' | 'active_users' | 'wedding_planners' | 'trial_users' | 'premium_users';
