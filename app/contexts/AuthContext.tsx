'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
    bootstrapAdminAuthToken,
    clearAdminAuthStorage,
    persistAdminAuthToken,
} from '@/utils/adminAuthStorage';

export interface UserProfile {
    id?: string;
    email: string;
    role: string;
    is_root_admin: boolean;
    is_wedding_planner: boolean;
    is_vendor: boolean;
    is_team_member: boolean;
    user_data?: any;
    profile_image_url?: string;
    first_name?: string;
    last_name?: string;
    timezone?: string; // IANA timezone string (e.g., 'America/Chicago')
    // Onboarding fields (for wedding planners)
    onboarding_completed?: boolean;
    onboarding_completed_at?: string;
    onboarding_steps_completed?: string[];
    // Team member fields (when role is team_member)
    team_permissions?: Record<string, boolean>;
    team_wedding_access?: string;
    team_assigned_wedding_ids?: string[];
    parent_planner_id?: string;
}

type AuthContextType = {
    isAuthenticated: boolean;
    isLoading: boolean;
    token: string | null;
    userProfile: UserProfile | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        const bootstrapAuth = async () => {
            const hydratedToken = await bootstrapAdminAuthToken();
            if (!cancelled && hydratedToken) {
                setToken(hydratedToken);
            }

            if (!cancelled) {
                setIsLoading(false);
            }
        };

        bootstrapAuth();

        return () => {
            cancelled = true;
        };
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
                cache: 'no-store', // Force fresh request, no caching
                credentials: 'include',
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
                credentials: 'include',
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
                credentials: 'include',
            });

            if (profileResponse.ok) {
                const profile = await profileResponse.json();
                setUserProfile(profile);

                toast.success('Login successful');

                // Use window.location.href for immediate navigation to avoid race condition with AdminRouteGuard
                // Redirect based on user role
                if (profile.is_root_admin) {
                    window.location.href = '/admin';
                } else if (profile.is_wedding_planner) {
                    window.location.href = '/admin/planner';
                } else if (profile.is_team_member) {
                    window.location.href = '/admin/planner';
                } else {
                    // Unknown/undefined role — do not grant access
                    console.error('Login rejected: unrecognized user role', profile.role);
                    clearAdminAuthStorage();
                    setToken(null);
                    setUserProfile(null);
                    toast.error('Your account role is not recognized. Please contact support.');
                    return;
                }
            } else {
                // Profile fetch failed — do not grant access without a confirmed role
                console.error('Profile fetch failed after login');
                clearAdminAuthStorage();
                setToken(null);
                toast.error('Unable to verify your account. Please try again.');
                return;
            }
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    };

    const logout = () => {
        const baseUrl = getApiBaseUrl();
        void fetch(`${baseUrl}/admin/logout`, {
            method: 'POST',
            credentials: 'include',
        }).catch(() => {});

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

    return (
        <AuthContext.Provider
            value={{
                isAuthenticated: !!token,
                isLoading,
                token,
                userProfile,
                login,
                logout,
                fetchUserProfile,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};
