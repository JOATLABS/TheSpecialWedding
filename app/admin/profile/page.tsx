'use client';

import React, { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';

interface UserProfile {
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  role: string;
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

export default function ProfilePage() {
  const { token } = useAdmin();
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

  useEffect(() => {
    fetchUserProfile();
  }, [token]);

  const fetchUserProfile = async () => {
    if (!token) return;

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
        setEmailData({ ...emailData, new_email: profile.email });
      }
    } catch (error) {
      console.error('Failed to fetch profile:', error);
      toast.error('Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (passwordData.new_password !== passwordData.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/profile/password`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        },
        body: JSON.stringify(passwordData),
        cache: 'no-store'
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
    }
  };

  const handleEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/profile/email`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        },
        body: JSON.stringify(emailData),
        cache: 'no-store'
      });

      if (response.ok) {
        toast.success('Email updated successfully');
        fetchUserProfile(); // Refresh profile
        setEmailData({ ...emailData, password: '' });
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update email');
      }
    } catch (error) {
      console.error('Email change failed:', error);
      toast.error('Email change failed');
    }
  };

  const handleProfileUpdate = async () => {
    try {
      const updateData = {
        first_name: profileData.first_name,
        last_name: profileData.last_name,
        company_name: profileData.company_name
      };

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/profile/info`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        },
        body: JSON.stringify(updateData),
        cache: 'no-store'
      });

      if (response.ok) {
        const result = await response.json();
        toast.success('Profile updated successfully');
        fetchUserProfile(); // Refresh profile data
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update profile');
      }
    } catch (error) {
      console.error('Profile update failed:', error);
      toast.error('Profile update failed');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4"></div>
          <p className="text-gray-600">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (!userProfile) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-600">Failed to load profile</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 to-rose-100 p-4 sm:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl sm:text-3xl font-heading text-wedding-rose mb-8">Account Settings</h1>
        
        <div className="bg-white rounded-lg shadow-lg p-6">
          {/* Tab Navigation */}
          {/* Mobile: Dropdown Select */}
          <div className="sm:hidden py-4">
            <select
              value={activeTab}
              onChange={(e) => setActiveTab(e.target.value as 'profile' | 'password' | 'email')}
              className="block w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md shadow-sm text-sm"
            >
              <option value="profile">Profile Info</option>
              <option value="password">Change Password</option>
              <option value="email">Change Email</option>
            </select>
          </div>

          {/* Desktop: Tab Navigation */}
          <div className="hidden sm:flex space-x-1 mb-6 border-b">
            <button
              onClick={() => setActiveTab('profile')}
              className={`px-4 py-2 font-medium text-sm rounded-t-lg ${
                activeTab === 'profile'
                  ? 'bg-wedding-rose text-white'
                  : 'text-gray-500 hover:text-wedding-rose'
              }`}
            >
              Profile Info
            </button>
            <button
              onClick={() => setActiveTab('password')}
              className={`px-4 py-2 font-medium text-sm rounded-t-lg ${
                activeTab === 'password'
                  ? 'bg-wedding-rose text-white'
                  : 'text-gray-500 hover:text-wedding-rose'
              }`}
            >
              Change Password
            </button>
            <button
              onClick={() => setActiveTab('email')}
              className={`px-4 py-2 font-medium text-sm rounded-t-lg ${
                activeTab === 'email'
                  ? 'bg-wedding-rose text-white'
                  : 'text-gray-500 hover:text-wedding-rose'
              }`}
            >
              Change Email
            </button>
          </div>

          {/* Profile Info Tab */}
          {activeTab === 'profile' && (
            <div>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Profile Information</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={userProfile.email}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Use the "Change Email" tab to modify</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Role
                  </label>
                  <input
                    type="text"
                    value={userProfile.role.replace('_', ' ').toUpperCase()}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    value={profileData.first_name}
                    onChange={(e) => setProfileData({...profileData, first_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    placeholder="Enter first name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Last Name
                  </label>
                  <input
                    type="text"
                    value={profileData.last_name}
                    onChange={(e) => setProfileData({...profileData, last_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    placeholder="Enter last name"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={profileData.company_name}
                    onChange={(e) => setProfileData({...profileData, company_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    placeholder="Enter company name"
                  />
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="button"
                  className="bg-wedding-rose text-white px-6 py-2 rounded-md hover:bg-wedding-gold transition"
                  onClick={handleProfileUpdate}
                >
                  Update Profile
                </button>
              </div>
            </div>
          )}

          {/* Change Password Tab */}
          {activeTab === 'password' && (
            <form onSubmit={handlePasswordChange}>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Change Password</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Current Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.current_password}
                    onChange={(e) => setPasswordData({...passwordData, current_password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    New Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.new_password}
                    onChange={(e) => setPasswordData({...passwordData, new_password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Must be at least 8 characters with uppercase, lowercase, number, and special character
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.confirm_password}
                    onChange={(e) => setPasswordData({...passwordData, confirm_password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    required
                  />
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="submit"
                  className="bg-wedding-rose text-white px-6 py-2 rounded-md hover:bg-wedding-gold transition"
                >
                  Change Password
                </button>
              </div>
            </form>
          )}

          {/* Change Email Tab */}
          {activeTab === 'email' && (
            <form onSubmit={handleEmailChange}>
              <h2 className="text-xl font-semibold text-gray-800 mb-4">Change Email Address</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Current Email
                  </label>
                  <input
                    type="email"
                    value={userProfile.email}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    New Email Address
                  </label>
                  <input
                    type="email"
                    value={emailData.new_email}
                    onChange={(e) => setEmailData({...emailData, new_email: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Current Password (for confirmation)
                  </label>
                  <input
                    type="password"
                    value={emailData.password}
                    onChange={(e) => setEmailData({...emailData, password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Enter your current password to confirm this change
                  </p>
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="submit"
                  className="bg-wedding-rose text-white px-6 py-2 rounded-md hover:bg-wedding-gold transition"
                >
                  Change Email
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}