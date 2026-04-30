'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { X, Camera, Trash2, Eye, EyeOff, Loader2, Bell, BellOff } from 'lucide-react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';

interface AccountSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface UserProfile {
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  role: string;
  profile_image_url?: string;
  push_notifications_enabled?: boolean;
  // Surfaced when an email-change request is in flight but not yet
  // verified by the user clicking the verification link.
  pending_email?: string;
  email_change_requested_at?: string;
  email_change_token_expires?: string;
}

interface ChangePasswordData {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

interface ChangeEmailData {
  new_email: string;
  password: string;
}

interface ProfileUpdateData {
  first_name: string;
  last_name: string;
  company_name: string;
}

export default function AccountSettingsModal({ isOpen, onClose }: AccountSettingsModalProps) {
  const { token, fetchUserProfile: refreshContextProfile } = useAdmin();
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'email'>('profile');

  // Form states
  const [passwordData, setPasswordData] = useState<ChangePasswordData>({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [emailData, setEmailData] = useState<ChangeEmailData>({
    new_email: '',
    password: ''
  });
  const [profileData, setProfileData] = useState<ProfileUpdateData>({
    first_name: '',
    last_name: '',
    company_name: ''
  });

  // Password visibility
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showEmailPassword, setShowEmailPassword] = useState(false);

  // Image upload states
  const [imageUploading, setImageUploading] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  // Push notifications state
  const [pushNotificationsEnabled, setPushNotificationsEnabled] = useState(true);
  const [savingPushSettings, setSavingPushSettings] = useState(false);
  const [browserPushSupported, setBrowserPushSupported] = useState(true);
  const [browserPushPermission, setBrowserPushPermission] = useState<NotificationPermission | null>(null);

  // Form submission states
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [cancellingPendingEmail, setCancellingPendingEmail] = useState(false);

  const fetchUserProfile = useCallback(async () => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/profile?t=${Date.now()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        },
        cache: 'no-store'
      });

      if (response.ok) {
        const profile = await response.json();
        setUserProfile(profile);
        setProfileData({
          first_name: profile.first_name || '',
          last_name: profile.last_name || '',
          company_name: profile.company_name || ''
        });
        // Do NOT prefill new_email with the active email — that made every
        // reopen of the modal look like the change had been reverted, even
        // though it was just pending verification. Reset the field; the
        // current/pending state is now displayed separately above.
        setEmailData({ new_email: '', password: '' });
        // Initialize push notifications state (default to true if not set)
        setPushNotificationsEnabled(profile.push_notifications_enabled !== false);
      }
    } catch (error) {
      console.error('Failed to fetch profile:', error);
      toast.error('Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isOpen) {
      fetchUserProfile();
    }
  }, [isOpen, fetchUserProfile]);

  // Check browser push notification support and actual subscription state
  useEffect(() => {
    if (typeof window !== 'undefined' && isOpen) {
      const supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
      setBrowserPushSupported(supported);

      if (supported) {
        setBrowserPushPermission(Notification.permission);

        // Check actual browser subscription state
        const checkSubscription = async () => {
          try {
            const registration = await navigator.serviceWorker.getRegistration();
            if (registration) {
              const subscription = await registration.pushManager.getSubscription();
              // If browser has subscription, enable; if not, disable
              // This ensures toggle reflects actual state for THIS browser/device
              setPushNotificationsEnabled(!!subscription);
            } else {
              // No service worker registered = no subscription
              setPushNotificationsEnabled(false);
            }
          } catch (error) {
            console.error('Failed to check push subscription:', error);
            // Fall back to DB preference (already set in fetchUserProfile)
          }
        };

        checkSubscription();
      }
    }
  }, [isOpen]);

  // Reset form when closing
  useEffect(() => {
    if (!isOpen) {
      setActiveTab('profile');
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setImagePreview(null);
    }
  }, [isOpen]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordData.new_password !== passwordData.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }

    setSavingPassword(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/password`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(passwordData),
      });

      if (response.ok) {
        toast.success('Password updated successfully');
        setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update password');
      }
    } catch (error) {
      console.error('Password change failed:', error);
      toast.error('Password change failed');
    } finally {
      setSavingPassword(false);
    }
  };

  const handleEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();

    setSavingEmail(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/email`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(emailData),
      });

      if (response.ok) {
        const result = await response.json().catch(() => null);
        // The backend now stores `pending_email` and emails a
        // verification link; the change is NOT applied yet. Be honest about
        // that in the toast so users understand why the dashboard hasn't
        // updated.
        if (result?.verification_email_sent === false) {
          toast.warning(
            'Change requested, but we could not send the verification email. Try again or contact support.'
          );
        } else {
          toast.success(
            `Verification link sent to ${result?.pending_email || 'the new address'}. Click it to finish the change.`
          );
        }
        fetchUserProfile();
        refreshContextProfile();
        // Clear the form on success — pending state is shown in the
        // amber banner above, not by re-prefilling the field.
        setEmailData({ new_email: '', password: '' });
      } else {
        const error = await response.json().catch(() => null);
        toast.error(error?.detail || 'Failed to update email');
      }
    } catch (error) {
      console.error('Email change failed:', error);
      toast.error('Email change failed');
    } finally {
      setSavingEmail(false);
    }
  };

  const handleCancelPendingEmailChange = async () => {
    setCancellingPendingEmail(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/email/pending`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const result = await response.json().catch(() => null);
        toast.success(
          result?.message || 'Pending email change cancelled'
        );
        fetchUserProfile();
        refreshContextProfile();
      } else {
        const error = await response.json().catch(() => null);
        toast.error(error?.detail || 'Failed to cancel pending change');
      }
    } catch (error) {
      console.error('Cancel pending email change failed:', error);
      toast.error('Failed to cancel pending change');
    } finally {
      setCancellingPendingEmail(false);
    }
  };

  const handleProfileUpdate = async () => {
    setSavingProfile(true);
    try {
      const updateData = {
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        company_name: profileData.company_name
      };

      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/info`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        toast.success('Profile updated successfully');
        fetchUserProfile();
        refreshContextProfile();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update profile');
      }
    } catch (error) {
      console.error('Profile update failed:', error);
      toast.error('Profile update failed');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please select a valid image file (JPEG, PNG, GIF, or WebP)');
      return;
    }

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image size must be less than 5MB');
      return;
    }

    // Show preview
    const reader = new FileReader();
    reader.onload = (event) => {
      setImagePreview(event.target?.result as string);
    };
    reader.readAsDataURL(file);

    // Upload image
    setImageUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/image`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.ok) {
        toast.success('Profile image updated!');
        fetchUserProfile();
        refreshContextProfile();
        setImagePreview(null);
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to upload image');
        setImagePreview(null);
      }
    } catch (error) {
      console.error('Image upload failed:', error);
      toast.error('Failed to upload image');
      setImagePreview(null);
    } finally {
      setImageUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteImage = async () => {
    if (!confirm('Are you sure you want to remove your profile image?')) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/profile/image`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        toast.success('Profile image removed');
        fetchUserProfile();
        refreshContextProfile();
      } else {
        toast.error('Failed to remove image');
      }
    } catch (error) {
      toast.error('Failed to remove image');
    }
  };

  const handlePushNotificationsToggle = async () => {
    if (!browserPushSupported) {
      toast.error('Push notifications are not supported in this browser');
      return;
    }

    setSavingPushSettings(true);
    const baseUrl = getApiBaseUrl();

    try {
      if (!pushNotificationsEnabled) {
        // ENABLING push notifications

        // 1. Request notification permission
        const permission = await Notification.requestPermission();
        setBrowserPushPermission(permission);

        if (permission !== 'granted') {
          toast.error('Please allow notifications in your browser settings');
          setSavingPushSettings(false);
          return;
        }

        // 2. Register service worker
        const registration = await navigator.serviceWorker.register('/sw.js');
        await navigator.serviceWorker.ready;

        // 3. Get VAPID public key from backend
        const keyResponse = await fetch(`${baseUrl}/admin/web-push/vapid-public-key`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!keyResponse.ok) {
          throw new Error('Failed to get VAPID key from server');
        }

        const { vapid_public_key } = await keyResponse.json();
        if (!vapid_public_key) {
          throw new Error('VAPID key not configured on server');
        }

        // 4. Convert VAPID key to Uint8Array
        const urlBase64ToUint8Array = (base64String: string) => {
          const padding = '='.repeat((4 - base64String.length % 4) % 4);
          const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
          const rawData = window.atob(base64);
          const outputArray = new Uint8Array(rawData.length);
          for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
          }
          return outputArray;
        };

        // 5. Subscribe to push notifications
        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapid_public_key)
        });

        // 6. Send subscription to backend
        const subscribeResponse = await fetch(`${baseUrl}/admin/web-push/subscribe`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ subscription: subscription.toJSON() })
        });

        if (!subscribeResponse.ok) {
          throw new Error('Failed to save subscription');
        }

        // 7. Update user preference
        await fetch(`${baseUrl}/profile/info`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ push_notifications_enabled: true })
        });

        setPushNotificationsEnabled(true);
        toast.success('Push notifications enabled');

      } else {
        // DISABLING push notifications

        // 1. Unsubscribe from browser push
        const registration = await navigator.serviceWorker.getRegistration();
        if (registration) {
          const subscription = await registration.pushManager.getSubscription();
          if (subscription) {
            // Tell backend to remove subscription
            await fetch(`${baseUrl}/admin/web-push/unsubscribe`, {
              method: 'DELETE',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({ endpoint: subscription.endpoint })
            });

            // Unsubscribe locally
            await subscription.unsubscribe();
          }
        }

        // 2. Update user preference
        await fetch(`${baseUrl}/profile/info`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ push_notifications_enabled: false })
        });

        setPushNotificationsEnabled(false);
        toast.success('Push notifications disabled');
      }
    } catch (error) {
      console.error('Push notification toggle failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update notification settings';
      toast.error(errorMessage);
    } finally {
      setSavingPushSettings(false);
    }
  };

  // Generate initials for avatar fallback
  const getInitials = () => {
    const first = userProfile?.first_name?.charAt(0) || '';
    const last = userProfile?.last_name?.charAt(0) || '';
    if (first || last) return (first + last).toUpperCase();
    return userProfile?.email?.charAt(0).toUpperCase() || '?';
  };

  if (!isOpen) return null;

  // Use portal to render modal at body level, avoiding parent positioning issues
  const modalContent = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4" role="presentation">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="relative z-10 bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-modal-title"
        aria-describedby="settings-modal-description"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-200 dark:border-slate-700 bg-gradient-to-r from-wedding-rose/10 to-wedding-gold/10 dark:from-slate-700 dark:to-slate-800">
          <div>
            <h2 id="settings-modal-title" className="text-xl font-bold text-gray-900 dark:text-white">Account Settings</h2>
            <p id="settings-modal-description" className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Manage your profile and preferences</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/50 dark:hover:bg-slate-600 transition-colors"
            aria-label="Close account settings modal"
          >
            <X size={22} className="text-gray-600 dark:text-gray-300" aria-hidden="true" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-80px)]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-wedding-rose" />
            </div>
          ) : !userProfile ? (
            <div className="py-12 text-center text-red-600 dark:text-red-400">
              Failed to load profile
            </div>
          ) : (
            <div className="p-6">
              {/* Tab Navigation */}
              <div className="flex gap-2 mb-6 p-1 bg-gray-100 dark:bg-slate-700/50 rounded-lg" role="tablist">
                <button
                  onClick={() => setActiveTab('profile')}
                  className={`flex-1 px-4 py-2.5 font-medium text-sm rounded-md transition-all ${
                    activeTab === 'profile'
                      ? 'bg-white dark:bg-slate-600 text-wedding-rose shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                  }`}
                  role="tab"
                  aria-selected={activeTab === 'profile'}
                  aria-controls="profile-tab-content"
                  id="profile-tab"
                >
                  Profile Info
                </button>
                <button
                  onClick={() => setActiveTab('password')}
                  className={`flex-1 px-4 py-2.5 font-medium text-sm rounded-md transition-all ${
                    activeTab === 'password'
                      ? 'bg-white dark:bg-slate-600 text-wedding-rose shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                  }`}
                  role="tab"
                  aria-selected={activeTab === 'password'}
                  aria-controls="password-tab-content"
                  id="password-tab"
                >
                  Password
                </button>
                <button
                  onClick={() => setActiveTab('email')}
                  className={`flex-1 px-4 py-2.5 font-medium text-sm rounded-md transition-all ${
                    activeTab === 'email'
                      ? 'bg-white dark:bg-slate-600 text-wedding-rose shadow-sm'
                      : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                  }`}
                  role="tab"
                  aria-selected={activeTab === 'email'}
                  aria-controls="email-tab-content"
                  id="email-tab"
                >
                  Email
                </button>
              </div>

              {/* Profile Info Tab */}
              {activeTab === 'profile' && (
                <div className="space-y-6" id="profile-tab-content" role="tabpanel" aria-labelledby="profile-tab">
                  {/* Profile Image Section */}
                  <div className="flex items-center gap-6 pb-6 border-b border-gray-200 dark:border-slate-700">
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-wedding-rose to-wedding-gold flex items-center justify-center shadow-lg">
                        {imagePreview ? (
                          <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
                        ) : userProfile.profile_image_url ? (
                          <img src={userProfile.profile_image_url} alt="Profile" className="w-full h-full object-cover" />
                        ) : (
                          <span className="text-2xl font-bold text-white">{getInitials()}</span>
                        )}
                      </div>
                      {imageUploading && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50 rounded-full">
                          <Loader2 className="w-6 h-6 animate-spin text-white" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">Profile Photo</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Max size: 5MB</p>
                      <div className="flex gap-2">
                        <input
                          type="file"
                          id="modal-profile-image-upload"
                          accept="image/jpeg,image/png,image/gif,image/webp"
                          onChange={handleImageChange}
                          disabled={imageUploading}
                          className="sr-only"
                        />
                        <label
                          htmlFor="modal-profile-image-upload"
                          className="cursor-pointer inline-flex items-center gap-1 bg-wedding-rose text-white px-3 py-1.5 rounded-md hover:bg-wedding-gold transition text-xs font-medium"
                        >
                          <Camera size={14} />
                          {imageUploading ? 'Uploading...' : 'Upload'}
                        </label>
                        {userProfile.profile_image_url && (
                          <button
                            type="button"
                            onClick={handleDeleteImage}
                            className="inline-flex items-center gap-1 text-red-600 dark:text-red-400 px-3 py-1.5 rounded-md border border-red-300 dark:border-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 transition text-xs font-medium"
                          >
                            <Trash2 size={14} />
                            Remove
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Profile Fields */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Email Address
                      </label>
                      <input
                        type="email"
                        value={userProfile.email}
                        disabled
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-slate-700/50 text-gray-500 dark:text-gray-400 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Role
                      </label>
                      <input
                        type="text"
                        value={userProfile.role.replace('_', ' ').toUpperCase()}
                        disabled
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-slate-700/50 text-gray-500 dark:text-gray-400 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        First Name
                      </label>
                      <input
                        type="text"
                        value={profileData.first_name}
                        onChange={(e) => setProfileData({ ...profileData, first_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                        placeholder="Enter first name"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Last Name
                      </label>
                      <input
                        type="text"
                        value={profileData.last_name}
                        onChange={(e) => setProfileData({ ...profileData, last_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                        placeholder="Enter last name"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Company Name
                      </label>
                      <input
                        type="text"
                        value={profileData.company_name}
                        onChange={(e) => setProfileData({ ...profileData, company_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                        placeholder="Enter company name"
                      />
                    </div>
                  </div>

                  {/* Push Notifications Toggle */}
                  <div className="pt-4 border-t border-gray-200 dark:border-slate-700">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {pushNotificationsEnabled ? (
                          <Bell className="w-5 h-5 text-wedding-rose" />
                        ) : (
                          <BellOff className="w-5 h-5 text-gray-400" />
                        )}
                        <div>
                          <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                            Push Notifications
                          </h3>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {!browserPushSupported
                              ? 'Not supported in this browser'
                              : browserPushPermission === 'denied'
                              ? 'Blocked - enable in browser settings'
                              : 'Receive instant alerts for RSVPs, payments, and updates'}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={pushNotificationsEnabled}
                        aria-label="Push notifications"
                        onClick={handlePushNotificationsToggle}
                        disabled={savingPushSettings || !browserPushSupported || browserPushPermission === 'denied'}
                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2 ${
                          pushNotificationsEnabled ? 'bg-wedding-rose' : 'bg-gray-300 dark:bg-slate-600'
                        } ${savingPushSettings || !browserPushSupported || browserPushPermission === 'denied' ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >
                        {savingPushSettings ? (
                          <span className="pointer-events-none inline-flex h-5 w-5 items-center justify-center rounded-full bg-white shadow">
                            <Loader2 className="w-3 h-3 animate-spin text-wedding-rose" />
                          </span>
                        ) : (
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                              pushNotificationsEnabled ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="flex justify-end pt-4 border-t border-gray-200 dark:border-slate-700">
                    <button
                      onClick={handleProfileUpdate}
                      disabled={savingProfile}
                      className="bg-wedding-rose text-white px-6 py-2.5 rounded-lg hover:bg-wedding-gold transition-all text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-md hover:shadow-lg"
                    >
                      {savingProfile && <Loader2 className="w-4 h-4 animate-spin" />}
                      Save Changes
                    </button>
                  </div>
                </div>
              )}

              {/* Password Tab */}
              {activeTab === 'password' && (
                <form onSubmit={handlePasswordChange} className="space-y-4" id="password-tab-content" role="tabpanel" aria-labelledby="password-tab">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Current Password
                    </label>
                    <div className="relative">
                      <input
                        type={showCurrentPassword ? 'text' : 'password'}
                        value={passwordData.current_password}
                        onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                        required
                        className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                      />
                      <button
                        type="button"
                        onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        aria-label={showCurrentPassword ? "Hide current password" : "Show current password"}
                      >
                        {showCurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      New Password
                    </label>
                    <div className="relative">
                      <input
                        type={showNewPassword ? 'text' : 'password'}
                        value={passwordData.new_password}
                        onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                        required
                        minLength={8}
                        className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        aria-label={showNewPassword ? "Hide new password" : "Show new password"}
                      >
                        {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      value={passwordData.confirm_password}
                      onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={savingPassword}
                      className="bg-wedding-rose text-white px-4 py-2 rounded-md hover:bg-wedding-gold transition text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                    >
                      {savingPassword && <Loader2 className="w-4 h-4 animate-spin" />}
                      Update Password
                    </button>
                  </div>
                </form>
              )}

              {/* Email Tab */}
              {activeTab === 'email' && (
                <form onSubmit={handleEmailChange} className="space-y-4" id="email-tab-content" role="tabpanel" aria-labelledby="email-tab">
                  {/* Current email — read-only context so the user knows what they're changing FROM */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Current Email
                    </label>
                    <div className="px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-slate-800 text-gray-700 dark:text-gray-300 text-sm">
                      {userProfile?.email || '—'}
                    </div>
                  </div>

                  {/* Pending state banner — shown only when an unverified email
                      change is in flight on the user record. Lets the user see
                      that something is happening, confirms the address the
                      verification link was sent to, and offers a cancel path. */}
                  {userProfile?.pending_email && (
                    <div className="rounded-md border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200">
                      <p className="font-medium">Verification pending</p>
                      <p className="mt-1">
                        We sent a verification link to{' '}
                        <strong>{userProfile.pending_email}</strong>. Click the
                        link in that inbox to finalize the change. Until then,
                        your account email is still {userProfile.email}.
                      </p>
                      <button
                        type="button"
                        onClick={handleCancelPendingEmailChange}
                        disabled={cancellingPendingEmail}
                        className="mt-2 inline-flex items-center gap-2 text-amber-800 dark:text-amber-200 underline disabled:opacity-50"
                      >
                        {cancellingPendingEmail && <Loader2 className="w-3 h-3 animate-spin" />}
                        Cancel pending change
                      </button>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      New Email Address
                    </label>
                    <input
                      type="email"
                      value={emailData.new_email}
                      onChange={(e) => setEmailData({ ...emailData, new_email: e.target.value })}
                      placeholder="you@example.com"
                      autoComplete="email"
                      required
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    />
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      You'll receive a verification link at this address. The
                      change isn't applied until you click it.
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Confirm with Password
                    </label>
                    <div className="relative">
                      <input
                        type={showEmailPassword ? 'text' : 'password'}
                        value={emailData.password}
                        onChange={(e) => setEmailData({ ...emailData, password: e.target.value })}
                        required
                        className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                      />
                      <button
                        type="button"
                        onClick={() => setShowEmailPassword(!showEmailPassword)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                        aria-label={showEmailPassword ? "Hide password" : "Show password"}
                      >
                        {showEmailPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={savingEmail || !emailData.new_email || !emailData.password}
                      className="bg-wedding-rose text-white px-4 py-2 rounded-md hover:bg-wedding-gold transition text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                    >
                      {savingEmail && <Loader2 className="w-4 h-4 animate-spin" />}
                      Send verification email
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Render modal using portal to document.body
  if (typeof window === 'undefined') return null;
  return createPortal(modalContent, document.body);
}
