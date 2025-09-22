'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
// Removed unused createAutomationAttrs import

interface UserProfile {
    email: string;
    role: string;
    is_root_admin: boolean;
    is_wedding_planner: boolean;
    is_vendor: boolean;
    user_data?: any;
}

type AdminContextType = {
    isAuthenticated: boolean;
    token: string | null;
    userProfile: UserProfile | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<void>;
    apiRequest: (path: string, method?: string, body?: any) => Promise<any>;
};

const AdminContext = createContext<AdminContextType | null>(null);

export const AdminProvider = ({
    children,
    initialAuth = false
}: {
    children: React.ReactNode;
    initialAuth?: boolean;
}) => {
    const router = useRouter();
    // Start with false, let useEffect handle cookie check
    // This prevents hydration mismatches
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);

    useEffect(() => {
        // TWO-COOKIE PATTERN:
        // 1. admin_token: httpOnly cookie with actual JWT (not accessible here)
        // 2. admin_authenticated: readable cookie for client auth state

        // Check the client-readable auth cookie
        const match = document.cookie.match(/admin_authenticated=([^;]+)/);
        const cookieAuth = match ? match[1] === 'true' : false;

        if (cookieAuth) {
            setIsAuthenticated(true);
            // Try to get the token from localStorage/sessionStorage (from login response)
            const storedToken = localStorage.getItem('admin_token') ||
                              sessionStorage.getItem('admin_token');
            if (storedToken) {
                setToken(storedToken);
            }
        } else if (!initialAuth) {
            // No auth cookie and no server-side auth = user is logged out
            setIsAuthenticated(false);
            setToken(null);
            // Clean up any stale storage
            localStorage.removeItem('admin_token');
            sessionStorage.removeItem('admin_token');
        }
    }, [initialAuth]);

    // Automatically fetch user profile when token is set
    useEffect(() => {
        if (token && !userProfile) {
            fetchUserProfile();
        }
    }, [token, userProfile]);

    const apiRequest = async (path: string, method: string = 'GET', body?: any) => {
        if (!token) {
            throw new Error('No authentication token available');
        }

        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!baseUrl) {
            throw new Error('API base URL not configured');
        }

        const url = `${baseUrl}${path}`;
        const options: any = {
            method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        };

        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || `Request failed with status ${response.status}`);
        }

        return await response.json();
    };

    const fetchUserProfile = async () => {
        if (!token) return;

        try {
            // Use the Next.js API proxy route for profile
            // This ensures we're on the same origin and cookies work properly
            const response = await fetch(`/api/admin/profile?t=${Date.now()}`, {
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
    };

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
            // SECURITY: Clear any existing sessions first to prevent session mixing
            localStorage.removeItem('admin_token');
            sessionStorage.removeItem('admin_token');
            document.cookie = 'admin_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';

            // Use the Next.js API proxy route instead of calling backend directly
            // This ensures cookies are set on the same origin (localhost:3000)
            const loginUrl = '/api/admin/token';
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

            // Store token in localStorage or sessionStorage for API calls
            // Note: The actual secure token is in httpOnly cookie (not accessible)
            // This stored token is used for Authorization headers in API requests
            const storage = rememberMe ? localStorage : sessionStorage;
            storage.setItem('admin_token', access_token);

            // The server sets two cookies via Set-Cookie headers:
            // 1. admin_token: httpOnly cookie with JWT (secure, not readable)
            // 2. admin_authenticated: readable cookie for client state

            setToken(access_token);
            setIsAuthenticated(true);

            toast.success('Login successful');

            // Add automation attribute to document for state tracking
            document.body.setAttribute('data-auth-state', 'authenticated');
            if (userProfile?.role) {
                document.body.setAttribute('data-auth-role', userProfile.role);
            }

            // Use window.location for reliable navigation
            // router.push() doesn't always work in context
            window.location.href = '/admin';
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    };


    const logout = async () => {
        try {
            // Use the Next.js API proxy route for logout
            // This ensures cookies are cleared on the same origin
            await fetch('/api/admin/logout', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });
        } catch (err) {
            // Continue with logout even if API call fails
            console.error('Logout API call failed:', err);
        }

        // Clear all possible storage locations
        localStorage.clear(); // Clear ALL localStorage, not just admin_token
        sessionStorage.clear(); // Clear ALL sessionStorage

        // Clear ALL cookies, not just admin_token
        document.cookie.split(";").forEach(cookie => {
            const eqPos = cookie.indexOf("=");
            const name = eqPos > -1 ? cookie.substring(0, eqPos).trim() : cookie.trim();
            // Clear for current path and domain
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;`;
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${window.location.hostname}`;
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${window.location.hostname}`;
        });

        // Clear React state
        setToken(null);
        setUserProfile(null);
        setIsAuthenticated(false);

        // Clear authentication attributes from document
        document.body.removeAttribute('data-auth-state');
        document.body.removeAttribute('data-auth-role');

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
        <AdminContext.Provider
            value={{
                isAuthenticated: isAuthenticated,  // Use the state, not token presence
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

