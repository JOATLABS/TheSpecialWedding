'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import { getApiBaseUrl } from '@/utils/env';
import { usePathname, useRouter } from 'next/navigation';
import { toast } from 'sonner';

import {
    bootstrapAdminAuthToken,
    clearAdminAuthStorage,
    getTokenExpiresInMs,
    isTokenExpired,
    persistAdminAuthToken,
    refreshAdminAuthToken,
    wasAdminSessionRemembered,
} from '@/utils/adminAuthStorage';

export interface UserProfile {
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
    // Onboarding fields (for wedding planners)
    onboarding_completed?: boolean;
    onboarding_completed_at?: string;
    onboarding_steps_completed?: string[];
    // Subscription fields
    subscription_status?: string;
    trial_end_date?: string;
    _subscription_blocked?: boolean;
    _subscription_block_reason?: string;
    // Team member fields
    is_team_member?: boolean;
    team_member_id?: string;
    parent_planner_id?: string;
    team_permissions?: Record<string, boolean>;
    team_wedding_access?: 'all' | 'assigned';
    team_assigned_wedding_ids?: string[];
    team_owner_email?: string;
}

type AdminContextType = {
    // Auth properties
    isAuthenticated: boolean;
    isLoading: boolean;
    authStatus: 'loading' | 'authenticated' | 'unauthenticated';
    token: string | null;
    userProfile: UserProfile | null;
    // Auth methods
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: (options?: { message?: string; redirectTo?: string; showToast?: boolean }) => void;
    expireSession: (message?: string) => void;
    fetchUserProfile: () => Promise<void>;
    // API methods
    apiRequest: <T = any>(path: string, method?: string, body?: unknown) => Promise<T | undefined>;
};

const AdminContext = createContext<AdminContextType | null>(null);

/**
 * AdminProvider - Canonical auth/API provider for admin surfaces.
 */
export const AdminProvider = ({ children }: { children: React.ReactNode }) => {
    const router = useRouter();
    const pathname = usePathname();
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [authStatus, setAuthStatus] = useState<'loading' | 'authenticated' | 'unauthenticated'>('loading');
    const sessionCheckRef = useRef<Promise<'success' | 'unauthenticated' | 'error'> | null>(null);
    const lastSessionCheckAtRef = useRef(0);

    useEffect(() => {
        let cancelled = false;

        const bootstrapAuth = async () => {
            const hydratedToken = await bootstrapAdminAuthToken();

            if (!cancelled && hydratedToken) {
                setToken(hydratedToken);
                setAuthStatus('authenticated');
            } else if (!cancelled) {
                setAuthStatus('unauthenticated');
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

    // ---- logout must be defined before fetchUserProfile & apiRequest ----
    // Both call logout() on 401/403, so it needs to be in scope first.
    const logout = useCallback((options?: { message?: string; redirectTo?: string; showToast?: boolean }) => {
        const {
            message = 'Logged out successfully',
            redirectTo = '/admin/login',
            showToast = true,
        } = options ?? {};
        const baseUrl = getApiBaseUrl();
        void fetch(`${baseUrl}/admin/logout`, {
            method: 'POST',
            credentials: 'include',
        }).catch(() => {});

        // Clear admin-specific storage (localStorage, sessionStorage, cookie)
        clearAdminAuthStorage();

        // Clear React state
        setToken(null);
        setUserProfile(null);
        setAuthStatus('unauthenticated');

        if (showToast) {
            toast.success(message);
        }

        // Force complete page refresh to clear ALL cached data and state
        window.location.replace(redirectTo);
    }, []);

    const expireSession = useCallback((message = 'Session expired. Please sign in again.') => {
        const redirectTo = `/admin/login?message=${encodeURIComponent(message)}`;
        logout({
            message,
            redirectTo,
            showToast: false,
        });
    }, [logout]);

    const revalidateSession = useCallback(async (): Promise<'success' | 'unauthenticated' | 'error'> => {
        if (sessionCheckRef.current) {
            return sessionCheckRef.current;
        }

        sessionCheckRef.current = (async () => {
            try {
                const result = await refreshAdminAuthToken(token);

                if (result.status === 'success' && result.token) {
                    persistAdminAuthToken(result.token, wasAdminSessionRemembered());
                    setToken((current) => (current === result.token ? current : result.token));
                    setAuthStatus('authenticated');
                    return 'success';
                }

                if (result.status === 'unauthenticated') {
                    return 'unauthenticated';
                }

                return 'error';
            } catch {
                return 'error';
            } finally {
                sessionCheckRef.current = null;
            }
        })();

        return sessionCheckRef.current;
    }, [token]);

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

                // If user is a team member, fetch their team permissions
                if (profile.role === 'team_member' || profile.is_team_member === true) {
                    try {
                        const permissionsResponse = await fetch(`${baseUrl}/admin/team/permissions`, {
                            method: 'GET',
                            headers: {
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json',
                                'Cache-Control': 'no-cache, no-store, must-revalidate',
                                'Pragma': 'no-cache'
                            },
                            cache: 'no-store',
                            credentials: 'include',
                        });

                        if (permissionsResponse.ok) {
                            const permJson = await permissionsResponse.json();
                            // Endpoint uses dict_response() → {success, data: {...}}
                            const permData = permJson.data ?? permJson;
                            profile.is_team_member = true;
                            profile.team_permissions = permData.permissions;
                            profile.team_wedding_access = permData.wedding_access;
                            profile.team_assigned_wedding_ids = permData.assigned_wedding_ids;
                            profile.team_owner_email = permData.owner_email;
                        } else {
                            console.warn('Failed to fetch team permissions for team member');
                        }
                    } catch (error) {
                        console.warn('Error fetching team permissions:', error);
                    }
                }

                setUserProfile(profile);
                setAuthStatus('authenticated');
            } else if (response.status === 402) {
                // Subscription blocked — user is authenticated but expired/cancelled.
                // This shouldn't happen anymore since backend tags instead of 402s on profile,
                // but handle it gracefully as a safety net.
                console.warn('Subscription blocked (402) — redirecting to billing');
            } else if (response.status === 401) {
                // Token expired or invalid — session is dead
                expireSession();
            }
        } catch (error) {
            // Log error without exposing sensitive information
            // Only log if we have a token, to avoid noisy logs during login flow
            if (token) {
                console.error('Failed to fetch user profile');
            }
        }
    }, [token, expireSession]);

    // Always refresh the profile when the active token changes so role-sensitive
    // pages never act on a stale profile from a previous session.
    useEffect(() => {
        if (!token) {
            setUserProfile(null);
            setAuthStatus(isLoading ? 'loading' : 'unauthenticated');
            return;
        }

        fetchUserProfile();
    }, [fetchUserProfile, isLoading, token]);

    // ---- Automatic token refresh ----
    // Schedule a refresh ~5 minutes before the JWT expires so the session
    // stays alive while the user is active. When the token state updates,
    // components that depend on it can refetch or reconnect against the
    // refreshed cookie-backed session state.
    useEffect(() => {
        if (!token) return;

        const REFRESH_BUFFER_MS = 5 * 60 * 1000; // refresh 5 min before expiry
        const msUntilExpiry = getTokenExpiresInMs(token);

        // If token is already expired or will expire in < 30s, don't schedule
        if (msUntilExpiry < 30_000) return;

        const refreshIn = Math.max(msUntilExpiry - REFRESH_BUFFER_MS, 30_000);

        const timerId = setTimeout(async () => {
            try {
                const result = await refreshAdminAuthToken(token);

                if (result.status === 'success') {
                    persistAdminAuthToken(result.token, wasAdminSessionRemembered());
                    // Update React state — this triggers the effect again,
                    // scheduling the NEXT refresh and keeping client state
                    // aligned with the refreshed session cookie.
                    setToken(result.token);
                    setAuthStatus('authenticated');
                }
                // If refresh fails because the session is invalid, expire it.
                else if (result.status === 'unauthenticated') {
                    expireSession();
                }
            } catch {
                // Network error — do nothing, will retry on next mount/token change
            }
        }, refreshIn);

        return () => clearTimeout(timerId);
    }, [expireSession, token]);

    useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }

        const isPublicPage = pathname === '/admin/login' || pathname.startsWith('/admin/team/accept');
        if (isPublicPage) {
            return;
        }

        const maybeRevalidate = () => {
            if (document.hidden) {
                return;
            }

            const now = Date.now();
            if (now - lastSessionCheckAtRef.current < 15_000) {
                return;
            }
            lastSessionCheckAtRef.current = now;

            void (async () => {
                const hasSessionState = !!token || !!userProfile;
                const shouldCheck = hasSessionState || authStatus === 'authenticated' || (!!token && isTokenExpired(token));
                if (!shouldCheck) {
                    return;
                }

                const result = await revalidateSession();
                if (result === 'unauthenticated') {
                    expireSession();
                }
            })();
        };

        const handleVisibilityChange = () => {
            if (!document.hidden) {
                maybeRevalidate();
            }
        };

        window.addEventListener('focus', maybeRevalidate);
        window.addEventListener('pageshow', maybeRevalidate);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            window.removeEventListener('focus', maybeRevalidate);
            window.removeEventListener('pageshow', maybeRevalidate);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [authStatus, expireSession, pathname, revalidateSession, token, userProfile]);

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
        // SECURITY: Clear any existing sessions first to prevent session mixing
        clearAdminAuthStorage();
            setToken(null);
            setUserProfile(null);
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

            // Track the active token — may be replaced by a fresh one below
            let activeToken = access_token;

            // Immediately check if the token needs a refresh (edge case:
            // server issued a token with < 10 min remaining, e.g. during
            // rapid login/logout cycles or clock skew)
            const ttlMs = getTokenExpiresInMs(access_token);
            if (ttlMs > 0 && ttlMs < 10 * 60 * 1000) {
                // Token has < 10 min left — trigger a background refresh
                // so the useEffect scheduler doesn't race against expiry
                try {
                    const refreshResult = await refreshAdminAuthToken(access_token);
                    if (refreshResult.status === 'success') {
                        persistAdminAuthToken(refreshResult.token, rememberMe);
                        activeToken = refreshResult.token;
                    }
                } catch {
                    // Network error on refresh — proceed with login token
                }
            }

            // Fetch user profile to determine redirect location
            // Use activeToken (which may be the refreshed token) for this request
            const profileResponse = await fetch(`${baseUrl}/admin/profile`, {
                headers: {
                    'Authorization': `Bearer ${activeToken}`,
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
            });

            if (profileResponse.ok) {
                const profile = await profileResponse.json();

                // If user is a team member, fetch their team permissions
                if (profile.role === 'team_member' || profile.is_team_member === true) {
                    try {
                        const permissionsResponse = await fetch(`${baseUrl}/admin/team/permissions`, {
                            method: 'GET',
                            headers: {
                                'Authorization': `Bearer ${activeToken}`,
                                'Content-Type': 'application/json',
                            },
                            credentials: 'include',
                        });

                        if (permissionsResponse.ok) {
                            const permJson = await permissionsResponse.json();
                            // Endpoint uses dict_response() → {success, data: {...}}
                            const permData = permJson.data ?? permJson;
                            profile.is_team_member = true;
                            profile.team_permissions = permData.permissions;
                            profile.team_wedding_access = permData.wedding_access;
                            profile.team_assigned_wedding_ids = permData.assigned_wedding_ids;
                            profile.team_owner_email = permData.owner_email;
                        } else {
                            console.warn('Failed to fetch team permissions for team member');
                        }
                    } catch (error) {
                        console.warn('Error fetching team permissions:', error);
                    }
                }

                toast.success('Login successful');

                // Commit authenticated state before navigating so route guards,
                // SSE, and page-level fetches never see a half-finished login.
                flushSync(() => {
                    setToken(activeToken);
                    setUserProfile(profile);
                    setAuthStatus('authenticated');
                });

                // Use a client-side transition here. A hard browser reload
                // throws away the in-memory access token before the destination
                // route can hydrate, which caused the first-login bounce loop.
                const subscriptionStatus =
                    profile.user_data?.subscription_status ||
                    profile.subscription_status;
                const billingBlocked =
                    profile._subscription_blocked ||
                    ['expired', 'cancelled', 'suspended', 'pending_payment', 'pending', 'inactive'].includes(subscriptionStatus || '');

                if (profile.is_root_admin) {
                    router.replace('/admin');
                } else if (profile.is_wedding_planner || profile.role === 'team_member' || profile.is_team_member === true) {
                    if (billingBlocked && profile.is_wedding_planner) {
                        router.replace('/admin/planner/billing');
                        return;
                    }
                    router.replace('/admin/planner');
                } else {
                    // Unknown/undefined role — do not grant access
                    console.error('Login rejected: unrecognized user role', profile.role, profile);
                    clearAdminAuthStorage();
                    setToken(null);
                    setUserProfile(null);
                    setAuthStatus('unauthenticated');
                    toast.error('Your account role is not recognized. Please contact support.');
                    return;
                }
            } else if (profileResponse.status === 402) {
                // Subscription expired/cancelled — user IS authenticated but needs to upgrade.
                // Store token so they can access the upgrade page.
                // Parse the error to get subscription info
                let detail = 'Your subscription requires attention.';
                try {
                    const errData = await profileResponse.json();
                    detail = errData.detail || detail;
                } catch {}

                // We still need basic profile data. The backend now returns profile
                // even for expired users (tagged with _subscription_blocked).
                // Re-fetch — the backend no longer 402s on profile, it tags the user.
                const retryProfile = await fetch(`${baseUrl}/admin/profile`, {
                    headers: {
                        'Authorization': `Bearer ${access_token}`,
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                });

                if (retryProfile.ok) {
                    const profile = await retryProfile.json();
                    flushSync(() => {
                        setToken(activeToken);
                        setUserProfile(profile);
                        setAuthStatus('authenticated');
                    });
                }

                toast.warning(detail);
                router.replace('/admin/planner/billing');
                return;
            } else {
                // Profile fetch failed — do not grant access without a confirmed role
                console.error('Profile fetch failed after login');
                clearAdminAuthStorage();
                setToken(null);
                setAuthStatus('unauthenticated');
                toast.error('Unable to verify your account. Please try again.');
                return;
            }
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
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
            cache: 'no-store',
            credentials: 'include',
        });

        if (!response.ok) {
            // 401 = token invalid/expired — force logout and re-auth
            if (response.status === 401) {
                expireSession();
                return undefined;
            }
            // 402 = subscription expired/blocked — redirect to billing
            if (response.status === 402) {
                window.location.href = '/admin/planner/billing';
                return undefined;
            }
            // 403 = permission denied — don't logout, let the caller handle it
            // (user is authenticated but lacks permission for this resource)
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
                // Auth properties
                isAuthenticated: authStatus === 'authenticated' && !!token,
                isLoading,
                authStatus,
                token,
                userProfile,
                // Auth methods
                login,
                logout,
                expireSession,
                fetchUserProfile,
                // API methods
                apiRequest,
            }}
        >
            {children}
        </AdminContext.Provider>
    );
}

/**
 * useAdmin - Canonical combined auth + API hook for admin surfaces.
 */
export const useAdmin = () => {
    const context = useContext(AdminContext);
    if (!context) {
        throw new Error('useAdmin must be used within AdminProvider');
    }
    return context;
};
