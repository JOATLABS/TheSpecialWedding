'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { X, Camera, Trash2, Eye, EyeOff, Loader2 } from 'lucide-react';
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

  // Form submission states
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);

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
        setEmailData((prev) => ({ ...prev, new_email: profile.email }));
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
      const response = await fetch(`${baseUrl}/admin/profile/password`, {
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
      const response = await fetch(`${baseUrl}/admin/profile/email`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(emailData),
      });

      if (response.ok) {
        toast.success('Email updated successfully');
        fetchUserProfile();
        refreshContextProfile();
        setEmailData({ ...emailData, password: '' });
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update email');
      }
    } catch (error) {
      console.error('Email change failed:', error);
      toast.error('Email change failed');
    } finally {
      setSavingEmail(false);
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
      const response = await fetch(`${baseUrl}/admin/profile/info`, {
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
      const response = await fetch(`${baseUrl}/admin/profile/image`, {
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
      const response = await fetch(`${baseUrl}/admin/profile/image`, {
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

  // Generate initials for avatar fallback
  const getInitials = () => {
    const first = userProfile?.first_name?.charAt(0) || '';
    const last = userProfile?.last_name?.charAt(0) || '';
    if (first || last) return (first + last).toUpperCase();
    return userProfile?.email?.charAt(0).toUpperCase() || '?';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden m-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-slate-700">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Account Settings</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          >
            <X size={20} className="text-gray-500 dark:text-gray-400" />
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
              <div className="flex space-x-1 mb-6 border-b border-gray-200 dark:border-slate-700">
                <button
                  onClick={() => setActiveTab('profile')}
                  className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
                    activeTab === 'profile'
                      ? 'bg-wedding-rose text-white'
                      : 'text-gray-500 dark:text-gray-400 hover:text-wedding-rose'
                  }`}
                >
                  Profile Info
                </button>
                <button
                  onClick={() => setActiveTab('password')}
                  className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
                    activeTab === 'password'
                      ? 'bg-wedding-rose text-white'
                      : 'text-gray-500 dark:text-gray-400 hover:text-wedding-rose'
                  }`}
                >
                  Change Password
                </button>
                <button
                  onClick={() => setActiveTab('email')}
                  className={`px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
                    activeTab === 'email'
                      ? 'bg-wedding-rose text-white'
                      : 'text-gray-500 dark:text-gray-400 hover:text-wedding-rose'
                  }`}
                >
                  Change Email
                </button>
              </div>

              {/* Profile Info Tab */}
              {activeTab === 'profile' && (
                <div className="space-y-6">
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

                  <div className="flex justify-end">
                    <button
                      onClick={handleProfileUpdate}
                      disabled={savingProfile}
                      className="bg-wedding-rose text-white px-4 py-2 rounded-md hover:bg-wedding-gold transition text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                    >
                      {savingProfile && <Loader2 className="w-4 h-4 animate-spin" />}
                      Save Changes
                    </button>
                  </div>
                </div>
              )}

              {/* Password Tab */}
              {activeTab === 'password' && (
                <form onSubmit={handlePasswordChange} className="space-y-4">
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
                <form onSubmit={handleEmailChange} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      New Email Address
                    </label>
                    <input
                      type="email"
                      value={emailData.new_email}
                      onChange={(e) => setEmailData({ ...emailData, new_email: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    />
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
                      >
                        {showEmailPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={savingEmail}
                      className="bg-wedding-rose text-white px-4 py-2 rounded-md hover:bg-wedding-gold transition text-sm font-medium disabled:opacity-50 flex items-center gap-2"
                    >
                      {savingEmail && <Loader2 className="w-4 h-4 animate-spin" />}
                      Update Email
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
}
