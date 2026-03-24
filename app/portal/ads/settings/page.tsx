'use client';

import React, { useState, useEffect } from 'react';
import { useVendorAuth } from '../layout';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
  Settings,
  User,
  MapPin,
  Phone,
  Globe,
  Building2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Save,
  Bell,
  BellOff,
} from 'lucide-react';

const API_BASE = getApiBaseUrl();

const VENDOR_CATEGORIES = [
  'photographer', 'videographer', 'florist', 'caterer', 'baker', 'dj',
  'band', 'wedding_planner', 'decorator', 'venue', 'transportation',
  'officiant', 'hair_stylist', 'makeup_artist', 'jeweler', 'stationer',
  'rental', 'photo_booth', 'lighting', 'other',
];

function formatCategory(cat: string) {
  return cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ProfileCompleteness {
  is_complete: boolean;
  missing_fields: string[];
  completion_percentage: number;
  total_fields: number;
  completed_fields: number;
}

interface VendorProfile {
  vendor_id: string;
  email: string;
  business_name: string;
  vendor_category: string;
  vendor_location: string;
  vendor_phone: string;
  vendor_website: string;
  vendor_description: string;
  logo_url: string;
  portfolio_urls: string[];
  vendor_account_status: string;
  is_free_tier: boolean;
  profile_completeness: ProfileCompleteness;
  created_at: string;
  profile_completed_at: string | null;
}

export default function VendorSettingsPage() {
  const { token } = useVendorAuth();
  const [profile, setProfile] = useState<VendorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Form fields
  const [businessName, setBusinessName] = useState('');
  const [category, setCategory] = useState('');
  const [location, setLocation] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [logoUrl, setLogoUrl] = useState('');

  // Push notification state
  const [pushSupported, setPushSupported] = useState(false);
  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [pushLoading, setPushLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetchProfile();
    checkPushStatus();
  }, [token]);

  async function checkPushStatus() {
    // Check browser support
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setPushSupported(false);
      return;
    }
    setPushSupported(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/vendors/web-push/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setPushSubscribed(data.subscribed);
      }
    } catch {
      // Silently fail
    }
  }

  async function togglePush() {
    if (!token) return;
    setPushLoading(true);

    try {
      if (pushSubscribed) {
        // Unsubscribe
        const res = await fetch(`${API_BASE}/api/v1/vendors/web-push/unsubscribe`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({}),
        });
        if (res.ok) {
          setPushSubscribed(false);
          toast.success('Push notifications disabled');
        }
      } else {
        // Get VAPID key
        const keyRes = await fetch(`${API_BASE}/api/v1/vendors/web-push/vapid-public-key`);
        if (!keyRes.ok) throw new Error('Push not configured on server');
        const { vapid_public_key } = await keyRes.json();

        // Request permission
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          toast.error('Notification permission denied');
          return;
        }

        // Subscribe via service worker
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: vapid_public_key,
        });

        // Send subscription to server
        const subRes = await fetch(`${API_BASE}/api/v1/vendors/web-push/subscribe`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ subscription: subscription.toJSON() }),
        });
        if (!subRes.ok) throw new Error('Failed to save subscription');

        setPushSubscribed(true);
        toast.success('Push notifications enabled');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to toggle push notifications');
    } finally {
      setPushLoading(false);
    }
  }

  async function fetchProfile() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/vendors/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to load profile');
      const data: VendorProfile = await res.json();
      setProfile(data);
      setBusinessName(data.business_name || '');
      setCategory(data.vendor_category || '');
      setLocation(data.vendor_location || '');
      setPhone(data.vendor_phone || '');
      setWebsite(data.vendor_website || '');
      setDescription(data.vendor_description || '');
      setLogoUrl(data.logo_url || '');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);

    try {
      const updates: Record<string, any> = {};
      if (businessName !== (profile?.business_name || '')) updates.business_name = businessName;
      if (category !== (profile?.vendor_category || '')) updates.vendor_category = category;
      if (location !== (profile?.vendor_location || '')) updates.vendor_location = location;
      if (phone !== (profile?.vendor_phone || '')) updates.vendor_phone = phone;
      if (website !== (profile?.vendor_website || '')) updates.vendor_website = website;
      if (description !== (profile?.vendor_description || '')) updates.vendor_description = description;
      if (logoUrl !== (profile?.logo_url || '')) updates.logo_url = logoUrl;

      if (Object.keys(updates).length === 0) {
        toast.info('No changes to save.');
        setSaving(false);
        return;
      }

      const res = await fetch(`${API_BASE}/api/v1/vendors/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update profile');
      }

      const result = await res.json();
      toast.success('Profile updated successfully');

      // Refresh profile to get updated completeness
      await fetchProfile();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const completeness = profile?.profile_completeness;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Settings className="w-6 h-6" />
          Business Profile
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          Complete your profile to start creating advertising campaigns.
        </p>
      </div>

      {/* Profile Completeness Banner */}
      {completeness && (
        <div className={`rounded-xl p-4 border ${
          completeness.is_complete
            ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800'
            : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
        }`}>
          <div className="flex items-center gap-3">
            {completeness.is_complete ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${
                completeness.is_complete
                  ? 'text-emerald-700 dark:text-emerald-300'
                  : 'text-amber-700 dark:text-amber-300'
              }`}>
                {completeness.is_complete
                  ? 'Profile complete — you can create campaigns!'
                  : `Profile ${completeness.completion_percentage}% complete`}
              </p>
              {!completeness.is_complete && completeness.missing_fields.length > 0 && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  Missing: {completeness.missing_fields.map(f => f.replace(/_/g, ' ')).join(', ')}
                </p>
              )}
            </div>
            {/* Progress bar */}
            <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden shrink-0">
              <div
                className={`h-full rounded-full transition-all ${
                  completeness.is_complete ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
                style={{ width: `${completeness.completion_percentage}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Profile Form */}
      <form onSubmit={handleSave} className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-6 space-y-5">
        {/* Business Name */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
            <Building2 className="w-4 h-4" />
            Business Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="Your Business Name"
          />
        </div>

        {/* Category */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
            <User className="w-4 h-4" />
            Service Category <span className="text-red-400">*</span>
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">Select a category...</option>
            {VENDOR_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>{formatCategory(cat)}</option>
            ))}
          </select>
        </div>

        {/* Location */}
        <div>
          <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
            <MapPin className="w-4 h-4" />
            Service Location <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="e.g. New York, NY"
          />
        </div>

        {/* Phone + Website */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
              <Phone className="w-4 h-4" />
              Phone
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="+1-555-0123"
            />
          </div>
          <div>
            <label className="flex items-center gap-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
              <Globe className="w-4 h-4" />
              Website
            </label>
            <input
              type="url"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="https://..."
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
            Business Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none"
            placeholder="Tell wedding planners about your services..."
          />
        </div>

        {/* Logo URL */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
            Logo URL
          </label>
          <input
            type="url"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            className="w-full px-3 py-2.5 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="https://example.com/logo.png"
          />
        </div>

        {/* Push Notifications */}
        {pushSupported && (
          <div className="flex items-center justify-between py-3 px-4 border border-slate-200 dark:border-slate-600 rounded-lg">
            <div className="flex items-center gap-2">
              {pushSubscribed ? (
                <Bell className="w-4 h-4 text-emerald-500" />
              ) : (
                <BellOff className="w-4 h-4 text-slate-400" />
              )}
              <div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  Push Notifications
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {pushSubscribed
                    ? 'You will receive browser notifications for new leads and campaign updates.'
                    : 'Enable to get instant browser alerts for new leads and campaign updates.'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={togglePush}
              disabled={pushLoading}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                pushSubscribed ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  pushSubscribed ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={saving}
          className="w-full py-2.5 bg-primary-500 hover:bg-primary-600 text-white font-medium rounded-lg transition-colors disabled:opacity-50 text-sm flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Profile
            </>
          )}
        </button>
      </form>
    </div>
  );
}
