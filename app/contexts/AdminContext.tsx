'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { clearAdminAuthStorage, persistAdminAuthToken } from '@/utils/adminAuthStorage';

interface UserProfile {
    id?: string;
    email: string;
    role: string;
    is_root_admin: boolean;
    is_wedding_planner: boolean;
    is_vendor: boolean;
    user_data?: any;
    profile_image_url?: string;
    first_name?: string;
    last_name?: string;
    timezone?: string; // IANA timezone string (e.g., 'America/Chicago')
}

type AdminContextType = {
    isAuthenticated: boolean;
    isLoading: boolean;
    token: string | null;
    userProfile: UserProfile | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<void>;
    apiRequest: <T = any>(path: string, method?: string, body?: unknown) => Promise<T | undefined>;
};

const AdminContext = createContext<AdminContextType | null>(null);

export const AdminProvider = ({ children }: { children: React.ReactNode }) => {
    const router = useRouter();
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Check localStorage first
        let stored = localStorage.getItem('admin_token');

        // If not in localStorage, check sessionStorage
        if (!stored) {
            stored = sessionStorage.getItem('admin_token');
        }

        // If not in storage, check cookies as fallback
        if (!stored) {
            const match = document.cookie.match(/admin_token=([^;]+)/);
            stored = match ? match[1] : null;
        }

        if (stored) {
            setToken(stored);
        }

        // Mark loading as complete - auth check is done
        setIsLoading(false);
    }, []);

    const fetchUserProfile = useCallback(async () => {
        if (!token) return;

        try {
            const baseUrl = getApiBaseUrl();
            const response = await fetch(`${baseUrl}/admin/profile?t=${Date.now()}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache'
                },
                cache: 'no-store' // Force fresh request, no caching
            });

            if (response.ok) {
                const profile = await response.json();
                setUserProfile(profile);
            }
        } catch (error) {
            // Log error without exposing sensitive information
            // Only log if we have a token, to avoid noisy logs during login flow
            if (token) {
                console.error('Failed to fetch user profile');
            }
        }
    }, [token]);

    // Automatically fetch user profile when token is set
    useEffect(() => {
        if (token && !userProfile) {
            fetchUserProfile();
        }
    }, [fetchUserProfile, token, userProfile]);

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
        // SECURITY: Clear any existing sessions first to prevent session mixing
        clearAdminAuthStorage();
            const baseUrl = getApiBaseUrl();
            const loginUrl = `${baseUrl}/admin/token`;
            const res = await fetch(loginUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Login failed');
            }

            const { access_token } = await res.json();

            persistAdminAuthToken(access_token, rememberMe);

            setToken(access_token);

            // Fetch user profile to determine redirect location
            const profileResponse = await fetch(`${baseUrl}/admin/profile`, {
                headers: {
                    'Authorization': `Bearer ${access_token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (profileResponse.ok) {
                const profile = await profileResponse.json();
                setUserProfile(profile);

                toast.success('Login successful');

                // Use window.location.href for immediate navigation to avoid race condition with AdminRouteGuard
                // Redirect based on user role
                if (profile.is_wedding_planner) {
                    window.location.href = '/admin/planner';
                } else {
                    window.location.href = '/admin';
                }
            } else {
                toast.success('Login successful');
                window.location.href = '/admin';
            }
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    };


    const logout = () => {
        // Clear all possible storage locations
        clearAdminAuthStorage();
        localStorage.clear(); // Clear ALL localStorage, not just admin_token
        sessionStorage.clear(); // Clear ALL sessionStorage
        
        // Clear React state
        setToken(null);
        setUserProfile(null);
        // Clear any cached API responses by making a dummy request
        try {
            fetch('/api/clear-cache', { method: 'POST' }).catch(() => {});
        } catch (error) {
            // Ignore cache clear errors
        }

        toast.success('Logged out successfully');

        // Force complete page refresh to clear ALL cached data and state
        window.location.href = '/admin/login';
    };

    const apiRequest = async <T = any>(path: string, method = 'GET', body?: unknown): Promise<T | undefined> => {
        if (!token) {
            throw new Error('Authentication required');
        }

        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}${path}`, {
            method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: body !== undefined ? JSON.stringify(body) : undefined,
            cache: 'no-store'
        });

        if (!response.ok) {
            const detail = await response.text();
            throw new Error(detail || 'Request failed');
        }

        if (response.status === 204 || response.status === 205) {
            return undefined;
        }

        const contentLength = response.headers.get('Content-Length');
        if (contentLength && Number.parseInt(contentLength, 10) === 0) {
            return undefined;
        }

        const contentType = response.headers.get('Content-Type') || '';
        const rawBody = await response.text();

        if (!rawBody.trim()) {
            return undefined;
        }

        if (contentType.toLowerCase().includes('json')) {
            try {
                return JSON.parse(rawBody) as T;
            } catch (error) {
                console.error('Failed to parse JSON response for', path, error);
                throw new Error('Invalid JSON response from server');
            }
        }

        return rawBody as unknown as T;
    };

    return (
        <AdminContext.Provider
            value={{
                isAuthenticated: !!token,
                isLoading,
                token,
                userProfile,
                login,
                logout,
                fetchUserProfile,
                apiRequest,
            }}
        >
            {children}
        </AdminContext.Provider>
    );
};

export const useAdmin = () => {
    const context = useContext(AdminContext);
    if (!context) {
        throw new Error('useAdmin must be used within AdminProvider');
    }
    return context;
};

