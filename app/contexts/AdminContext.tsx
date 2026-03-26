'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import {
    bootstrapAdminAuthToken,
    clearAdminAuthStorage,
    getTokenExpiresInMs,
    persistAdminAuthToken,
    wasAdminSessionRemembered,
} from '@/utils/adminAuthStorage';

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
    token: string | null;
    userProfile: UserProfile | null;
    // Auth methods
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<void>;
    // API methods
    apiRequest: <T = any>(path: string, method?: string, body?: unknown) => Promise<T | undefined>;
};

const AdminContext = createContext<AdminContextType | null>(null);

/**
 * AdminProvider - Composes AuthProvider and APIProvider
 * Maintains backward compatibility for existing consumers
 */
export const AdminProvider = ({ children }: { children: React.ReactNode }) => {
    const router = useRouter();
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

    // ---- logout must be defined before fetchUserProfile & apiRequest ----
    // Both call logout() on 401/403, so it needs to be in scope first.
    const logout = useCallback(() => {
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

        toast.success('Logged out successfully');

        // Force complete page refresh to clear ALL cached data and state
        window.location.href = '/admin/login';
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
            } else if (response.status === 402) {
                // Subscription blocked — user is authenticated but expired/cancelled.
                // This shouldn't happen anymore since backend tags instead of 402s on profile,
                // but handle it gracefully as a safety net.
                console.warn('Subscription blocked (402) — redirecting to billing');
            } else if (response.status === 401) {
                // Token expired or invalid — session is dead
                logout();
            }
        } catch (error) {
            // Log error without exposing sensitive information
            // Only log if we have a token, to avoid noisy logs during login flow
            if (token) {
                console.error('Failed to fetch user profile');
            }
        }
    }, [token, logout]);

    // Always refresh the profile when the active token changes so role-sensitive
    // pages never act on a stale profile from a previous session.
    useEffect(() => {
        if (!token) {
            setUserProfile(null);
            return;
        }

        fetchUserProfile();
    }, [fetchUserProfile, token]);

    // ---- Automatic token refresh ----
    // Schedule a refresh ~5 minutes before the JWT expires so the session
    // stays alive while the user is active. When the token state updates,
    // every component that depends on `token` (including TopHeader's SSE
    // EventSource) will automatically reconnect with the fresh JWT.
    useEffect(() => {
        if (!token) return;

        const REFRESH_BUFFER_MS = 5 * 60 * 1000; // refresh 5 min before expiry
        const msUntilExpiry = getTokenExpiresInMs(token);

        // If token is already expired or will expire in < 30s, don't schedule
        if (msUntilExpiry < 30_000) return;

        const refreshIn = Math.max(msUntilExpiry - REFRESH_BUFFER_MS, 30_000);

        const timerId = setTimeout(async () => {
            try {
                const baseUrl = getApiBaseUrl();
                const res = await fetch(`${baseUrl}/admin/token/refresh`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                });

                if (res.ok) {
                    const { access_token } = await res.json();
                    persistAdminAuthToken(access_token, wasAdminSessionRemembered());
                    // Update React state — this triggers the effect again,
                    // scheduling the NEXT refresh, and also causes TopHeader
                    // to reconnect SSE with the fresh token.
                    setToken(access_token);
                }
                // If refresh fails (e.g. 401 because the token expired in the
                // meantime), we do nothing — the next API call or profile fetch
                // will handle the 401 and trigger logout if needed.
            } catch {
                // Network error — do nothing, will retry on next mount/token change
            }
        }, refreshIn);

        return () => clearTimeout(timerId);
    }, [token]);

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
                    const refreshRes = await fetch(`${baseUrl}/admin/token/refresh`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${access_token}`,
                            'Content-Type': 'application/json',
                        },
                        credentials: 'include',
                    });
                    if (refreshRes.ok) {
                        const { access_token: fresh } = await refreshRes.json();
                        persistAdminAuthToken(fresh, rememberMe);
                        activeToken = fresh;
                        setToken(fresh);
                    } else {
                        // Refresh failed but login token is still valid — use it
                        setToken(access_token);
                    }
                } catch {
                    // Network error on refresh — proceed with login token
                    setToken(access_token);
                }
            } else {
                setToken(access_token);
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

                setUserProfile(profile);

                toast.success('Login successful');

                // Use window.location.href for immediate navigation to avoid race condition with AdminRouteGuard.
                // Root admins and planners land on different dashboard surfaces.
                if (profile.is_root_admin) {
                    window.location.href = '/admin';
                } else if (profile.is_wedding_planner || profile.role === 'team_member' || profile.is_team_member === true) {
                    window.location.href = '/admin/planner';
                } else {
                    // Unknown/undefined role — do not grant access
                    console.error('Login rejected: unrecognized user role', profile.role, profile);
                    clearAdminAuthStorage();
                    setToken(null);
                    setUserProfile(null);
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
                    setUserProfile(profile);
                }

                toast.warning(detail);
                window.location.href = '/admin/planner/billing';
                return;
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
                logout();
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
                isAuthenticated: !!token,
                isLoading,
                token,
                userProfile,
                // Auth methods
                login,
                logout,
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
 * useAdmin - Backward compatibility hook
 * Returns combined auth and API context
 *
 * For new code, prefer:
 * - useAuth() for authentication state and operations
 * - useAPI() for API requests
 */
export const useAdmin = () => {
    const context = useContext(AdminContext);
    if (!context) {
        throw new Error('useAdmin must be used within AdminProvider');
    }
    return context;
};
