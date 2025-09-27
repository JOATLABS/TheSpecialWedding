'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
// Removed unused useRouter import
import { toast } from 'sonner';
// Removed unused createAutomationAttrs import

export interface UserProfile {
    email: string;
    role: string;
    is_root_admin: boolean;
    is_wedding_planner: boolean;
    is_vendor: boolean;
    user_data?: any;
}

type AdminContextType = {
    isAuthenticated: boolean;
    isSessionInitialized: boolean;
    token: string | null;
    userProfile: UserProfile | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<UserProfile | null>;
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
    // Server-first authentication: middleware handles auth checks
    // Context only manages user profile state and login/logout actions
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(initialAuth);
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isSessionInitialized, setIsSessionInitialized] = useState(false);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }

        const readAuthCookie = () => {
            if (typeof document === 'undefined') {
                return false;
            }

            const match = document.cookie.match(/(?:^|;\s*)admin_authenticated=([^;]+)/);
            return match ? match[1] === 'true' : false;
        };

        const readStoredToken = () => {
            try {
                return localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
            } catch (error) {
                console.warn('Failed to read stored admin token', error);
                return null;
            }
        };

        const clearStoredToken = () => {
            try {
                localStorage.removeItem('admin_token');
                sessionStorage.removeItem('admin_token');
            } catch (error) {
                console.warn('Failed to clear stored admin token', error);
            }
        };

        const syncAuthState = () => {
            const hasAuthCookie = readAuthCookie();
            const storedToken = hasAuthCookie ? readStoredToken() : null;

            if (!hasAuthCookie) {
                clearStoredToken();
            }

            const nextToken = storedToken ?? null;
            setToken(nextToken);

            const isAuthenticatedState = Boolean(hasAuthCookie && nextToken);
            setIsAuthenticated(isAuthenticatedState);

            if (!isAuthenticatedState) {
                setUserProfile(null);
                if (typeof document !== 'undefined') {
                    document.body.removeAttribute('data-auth-state');
                    document.body.removeAttribute('data-auth-role');
                }
            } else if (typeof document !== 'undefined') {
                document.body.setAttribute('data-auth-state', 'authenticated');
            }

            setIsSessionInitialized(true);
        };

        const handleStorage = (event: StorageEvent) => {
            if (event.key === 'admin_token' || event.key === null) {
                syncAuthState();
            }
        };

        const handleFocus = () => {
            syncAuthState();
        };

        syncAuthState();

        window.addEventListener('storage', handleStorage);
        window.addEventListener('focus', handleFocus);

        return () => {
            window.removeEventListener('storage', handleStorage);
            window.removeEventListener('focus', handleFocus);
        };
    }, []);

    const apiRequest = useCallback(async (path: string, method: string = 'GET', body?: any) => {
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
    }, [token]);

    const fetchUserProfile = useCallback(async () => {
        if (!token) {
            return null;
        }

        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!baseUrl) {
            throw new Error('API base URL not configured');
        }

        try {
            const response = await fetch(`${baseUrl}/admin/profile?t=${Date.now()}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache'
                },
                cache: 'no-store'
            });

            if (response.status === 401) {
                if (typeof window !== 'undefined') {
                    try {
                        localStorage.removeItem('admin_token');
                        sessionStorage.removeItem('admin_token');
                    } catch (storageError) {
                        console.warn('Failed to clear auth tokens after unauthorized response', storageError);
                    }
                }
                setIsAuthenticated(false);
                setToken(null);
                setUserProfile(null);
                if (typeof document !== 'undefined') {
                    document.body.removeAttribute('data-auth-state');
                    document.body.removeAttribute('data-auth-role');
                }
                return null;
            }

            if (!response.ok) {
                const errorPayload = await response.json().catch(() => null);
                const message = errorPayload?.detail || `Request failed with status ${response.status}`;
                throw new Error(message);
            }

            const profile: UserProfile = await response.json();
            setUserProfile(profile);
            setIsAuthenticated(true);
            if (typeof document !== 'undefined') {
                document.body.setAttribute('data-auth-state', 'authenticated');
                if (profile.role) {
                    document.body.setAttribute('data-auth-role', profile.role);
                }
            }
            return profile;
        } catch (error) {
            console.error('Failed to fetch user profile', error);
            throw error;
        }
    }, [token]);

    const login = useCallback(async (email: string, password: string, rememberMe = true) => {
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
                credentials: 'include'
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Login failed');
            }

            const { access_token } = await res.json();

            // The server sets two cookies via Set-Cookie headers:
            // 1. admin_token: httpOnly cookie with JWT (secure, not readable)
            // 2. admin_authenticated: readable cookie for client state

            // Store token for API calls (used for Authorization headers)
            const storage = rememberMe ? localStorage : sessionStorage;
            storage.setItem('admin_token', access_token);

            setToken(access_token);
            setIsAuthenticated(true);

            toast.success('Login successful');

            // Add automation attribute to document for state tracking
            document.body.setAttribute('data-auth-state', 'authenticated');

            // Simple redirect - middleware will handle the rest
            window.location.href = '/admin';
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    }, []);


    const logout = useCallback(async () => {
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
    }, [token]);

    const contextValue = useMemo(() => ({
        isAuthenticated,
        isSessionInitialized,
        token,
        userProfile,
        login,
        logout,
        fetchUserProfile,
        apiRequest,
    }), [
        apiRequest,
        fetchUserProfile,
        isAuthenticated,
        isSessionInitialized,
        login,
        logout,
        token,
        userProfile,
    ]);

    return (
        <AdminContext.Provider value={contextValue}>
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

