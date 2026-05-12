'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { flushSync } from 'react-dom';
import { getApiBaseUrl } from '@/utils/env';
import { isBlockedSubscriptionStatus, normalizeSubscriptionStatus } from '@/utils/subscriptionStatus';
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
import { redirectOnBillingBlock } from '@/utils/adminApiAuthGuard';
import {
    DEFAULT_TEAM_MEMBER_BLOCK_REASON,
    isTeamMemberRole,
} from '@/utils/roles';

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
    // In-flight guard for /admin/profile (+ /admin/team/permissions
    // for team members).  Without this, the bootstrap useEffect, the
    // token-change useEffect, the token-refresh callback, and React
    // StrictMode's double-effect all overlap and fire 3-4 redundant
    // /admin/profile requests on every dashboard mount — a measurable
    // friction we observed live with one planner.  When set, callers
    // share the existing promise instead of spawning another round trip.
    const profileFetchRef = useRef<Promise<void> | null>(null);

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

    const fetchUserProfile = useCallback(async (): Promise<void> => {
        if (!token) return;

        // In-flight guard: when the bootstrap effect, token-change
        // effect, and token-refresh callback all fire in quick
        // succession (which is the normal pattern on dashboard mount,
        // amplified by React StrictMode's double-effect in dev), share
        // the in-flight promise instead of spawning another round trip.
        // Same pattern as ``revalidateSession`` above.
        if (profileFetchRef.current) {
            return profileFetchRef.current;
        }

        profileFetchRef.current = (async () => {
            try {
                const baseUrl = getApiBaseUrl();
                // Browser cache is allowed to honor the response's
                // Cache-Control header (set by the backend `add_cache_headers`
                // middleware).  The auth-extended Redis cache has a 10 s
                // TTL with explicit invalidation on Stripe webhooks, trial
                // expiry, and team-permission changes, so a stale profile
                // is bounded to 10 s.  The 2-minute subscription poll is a
                // third-line backstop.  The previous `?t=${Date.now()}` +
                // `cache: 'no-store'` combo bypassed every cache layer on
                // every request and was the dominant reason the dashboard
                // felt cold on every navigation.
                const response = await fetch(`${baseUrl}/admin/profile`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                });

                if (response.ok) {
                    const profile = await response.json();

                    // If user is a team member, fetch their team permissions
                    if (profile.role === 'team_member' || profile.is_team_member === true) {
                        try {
                            // Same cache rationale as `/admin/profile` above —
                            // permissions changes invalidate the auth cache via
                            // the team-management mutation hooks.
                            const permissionsResponse = await fetch(`${baseUrl}/admin/team/permissions`, {
                                method: 'GET',
                                headers: {
                                    'Authorization': `Bearer ${token}`,
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
            } finally {
                profileFetchRef.current = null;
            }
        })();

        return profileFetchRef.current;
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

    // ---- Periodic subscription status check for planners ----
    // Polls every 2 minutes to detect mid-session subscription changes
    // (e.g., cancellation via Stripe Portal while user is on dashboard).
    // This also keeps AdminRouteGuard's cached profile fresh (Finding #6).
    useEffect(() => {
        if (!token || !userProfile?.is_wedding_planner) return;

        const POLL_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes

        const checkSubscriptionStatus = async () => {
            try {
                const baseUrl = getApiBaseUrl();
                // The 2-minute interval below is the freshness
                // mechanism.  No need to additionally bypass browser
                // cache — the backend's short TTL on `/admin/profile`
                // ensures each poll hits a fresh assembly.
                const res = await fetch(`${baseUrl}/admin/profile`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                    },
                    credentials: 'include',
                });
                if (!res.ok) return;
                const data = await res.json();
                const freshStatus = normalizeSubscriptionStatus(
                    data.user_data?.subscription_status || data.subscription_status || ''
                );
                const currentStatus = normalizeSubscriptionStatus(
                    userProfile.subscription_status || ''
                );
                // Only trigger full refresh if status actually changed
                if (freshStatus && freshStatus !== currentStatus) {
                    fetchUserProfile();
                }
            } catch {
                // Silently ignore network errors — transient failures are fine
            }
        };

        const intervalId = setInterval(checkSubscriptionStatus, POLL_INTERVAL_MS);
        return () => clearInterval(intervalId);
    }, [token, userProfile?.is_wedding_planner, userProfile?.subscription_status, fetchUserProfile]);

    const login = useCallback(async (email: string, password: string, rememberMe = true) => {
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
                const err = await res.json().catch(() => ({}));
                const detail = err?.detail || 'Login failed';
                // Any non-2xx /admin/token response is an EXPECTED HTTP
                // failure — the server reached us and returned a structured
                // detail (401 "Invalid credentials", 402 subscription-block,
                // 403 disabled, 429 rate-limit, etc.). The login page renders
                // the detail inline via setError, so the catch block below
                // skips the `console.error("Login flow threw: ...")` +
                // redundant toast for these. Only true network failures
                // (fetch rejection, no `res` at all) should land in the noisy
                // branch. ``isAuthBlock`` retained as the legacy 402-only
                // tag for callers that key off it. See AGENTS.md → "Known
                // Open Issues" item 4.
                const loginError: Error & {
                    status?: number;
                    isAuthBlock?: boolean;
                    isExpectedHttpError?: boolean;
                } = new Error(detail);
                loginError.status = res.status;
                loginError.isExpectedHttpError = true;
                if (res.status === 402) {
                    loginError.isAuthBlock = true;
                }
                throw loginError;
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

                // ── RACE CONDITION FIX (Prong 2): Verify subscription status ──
                // If webhook hasn't updated users collection yet, the subscription
                // endpoint may have fresher data. Fetch it to override the profile if needed.
                let billingBlocked = false;
                if (profile.is_wedding_planner) {
                    try {
                        const subResponse = await fetch(`${baseUrl}/stripe/subscription`, {
                            method: 'GET',
                            headers: {
                                'Authorization': `Bearer ${activeToken}`,
                                'Content-Type': 'application/json',
                            },
                            credentials: 'include',
                        });

                        if (subResponse.ok) {
                            const subData = await subResponse.json();
                            const freshStatus = normalizeSubscriptionStatus(subData.status || subData.subscription_status);
                            if (isBlockedSubscriptionStatus(freshStatus)) {
                                console.info(`Subscription verification: endpoint returned blocked status '${freshStatus}', overriding profile`);
                                billingBlocked = true;
                            }
                        }
                    } catch (error) {
                        // Network error or endpoint unavailable — fall back to profile data
                        console.debug(`Could not verify subscription status: ${error}`);
                    }
                }

                // If subscription verification didn't set billingBlocked, check profile flags
                if (!billingBlocked) {
                    const subscriptionStatus =
                        normalizeSubscriptionStatus(
                            profile.user_data?.subscription_status ||
                            profile.subscription_status
                        );
                    billingBlocked =
                        profile._subscription_blocked ||
                        isBlockedSubscriptionStatus(subscriptionStatus);
                }

                // Use a client-side transition here. A hard browser reload
                // throws away the in-memory access token before the destination
                // route can hydrate, which caused the first-login bounce loop.

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
                // Profile fetch failed — do not grant access without a confirmed role.
                // Inline status/statusText/url/body into the primary message string so
                // the Next.js error overlay cannot swallow the object payload (it has
                // been observed rendering the second console.error arg as `{}`).
                let bodyText = '';
                try {
                    bodyText = await profileResponse.text();
                } catch {
                    bodyText = '<unable to read response body>';
                }
                const truncatedBody = bodyText.slice(0, 500);
                const debugLine =
                    `Profile fetch failed after login — ` +
                    `status=${profileResponse.status} ` +
                    `statusText="${profileResponse.statusText}" ` +
                    `url="${profileResponse.url}" ` +
                    `body="${truncatedBody.replace(/"/g, '\\"')}"`;
                console.error(debugLine);
                // Also log the structured form in case the overlay does expand it.
                console.error('Profile fetch failure details:', {
                    status: profileResponse.status,
                    statusText: profileResponse.statusText,
                    url: profileResponse.url,
                    body: truncatedBody,
                });
                clearAdminAuthStorage();
                setToken(null);
                setAuthStatus('unauthenticated');
                toast.error(
                    `Unable to verify your account (HTTP ${profileResponse.status}). Please try again or contact support.`,
                );
                return;
            }
        } catch (err: any) {
            // Expected HTTP responses (401 invalid creds, 402 subscription
            // block, 403 disabled, 429 rate-limit, etc.) are NOT network
            // failures. The login page already renders the detail inline
            // via setError, so we skip the console.error noise + duplicate
            // "network error" toast and just rethrow for the page handler.
            // See AGENTS.md → "Known Open Issues" item 4.
            if (err?.isExpectedHttpError || err?.isAuthBlock) {
                throw err;
            }
            // Network-level failure (fetch rejection — CORS, DNS, backend
            // down, etc.) lands here. Without this log, the only signal is
            // a toast, which leaves us blind.
            console.error(
                `Login flow threw: name="${err?.name}" message="${err?.message}" stack=${err?.stack}`,
            );
            toast.error(err.message || 'Login failed due to a network error');
            throw err;
        }
    }, [router]);

    const apiRequest = useCallback(async <T = any>(path: string, method = 'GET', body?: unknown): Promise<T | undefined> => {
        if (!token) {
            throw new Error('Authentication required');
        }

        const baseUrl = getApiBaseUrl();
        // Only force ``no-store`` on mutating methods — GETs are allowed
        // to honor the response's Cache-Control header (set by
        // ``add_cache_headers`` middleware).  Forcing ``no-store`` on
        // every GET defeated browser caching across the entire admin
        // app, which was the dominant cause of every navigation feeling
        // like a cold start.  Mutations stay uncached because their
        // responses must never be served from cache.
        const isMutation = method !== 'GET' && method !== 'HEAD';
        const response = await fetch(`${baseUrl}${path}`, {
            method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: body !== undefined ? JSON.stringify(body) : undefined,
            cache: isMutation ? 'no-store' : 'default',
            credentials: 'include',
        });

        if (!response.ok) {
            // 401 = token invalid/expired — force logout and re-auth
            if (response.status === 401) {
                expireSession();
                return undefined;
            }
            // 402 = subscription expired/blocked. Two distinct flows:
            //   - Planners: hard-redirect to /admin/planner/billing (the
            //     centralized helper handles this — they CAN self-serve resolve).
            //   - Team members: no self-serve path exists, only the planner
            //     can fix it. Logout and bounce to /admin/login?error=<reason>
            //     so Step 4's banner surfaces the reason inline. We must
            //     consume the JSON body before falling through to the helper
            //     so the team-member branch can preserve the backend detail.
            if (response.status === 402) {
                let paymentBody: any = null;
                try {
                    paymentBody = await response.clone().json();
                } catch {
                    paymentBody = null;
                }

                const detail = paymentBody?.detail;
                const nonBillingCode =
                    typeof detail === 'object' && detail !== null
                        ? detail.error
                        : paymentBody?.error;
                if (nonBillingCode === 'insufficient_credits') {
                    const message =
                        (typeof detail === 'object' && detail?.message) ||
                        paymentBody?.message ||
                        'Insufficient AI credits.';
                    throw new Error(message);
                }

                if (isTeamMemberRole(userProfile)) {
                    let reason = DEFAULT_TEAM_MEMBER_BLOCK_REASON;
                    if (
                        paymentBody &&
                        typeof paymentBody.detail === 'string' &&
                        paymentBody.detail.trim()
                    ) {
                        reason = paymentBody.detail;
                    }
                    logout({
                        message: reason,
                        redirectTo: `/admin/login?error=${encodeURIComponent(reason)}`,
                        showToast: false,
                    });
                    return undefined;
                }
                if (redirectOnBillingBlock(response)) {
                    return undefined;
                }
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
    }, [token, userProfile, expireSession, logout]);

    // Memoize the provider value so consumers (Sidebar, TopHeader,
    // AdminRouteGuard, every admin page reading `useAdmin()`) only
    // re-render when something they actually depend on changes.
    // Without this, the value object is rebuilt every render and every
    // consumer is forced through React's reconciliation on each state
    // tick — which is the core reason a single click felt sluggish
    // even with one planner and one wedding.  The deps list here is
    // the union of every primitive/object that contributes to the
    // exposed shape; the memoized callbacks (login/logout/etc.) carry
    // their own deps so they only change identity when meaningful.
    const value = useMemo<AdminContextType>(() => ({
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
    }), [
        authStatus,
        token,
        isLoading,
        userProfile,
        login,
        logout,
        expireSession,
        fetchUserProfile,
        apiRequest,
    ]);

    return (
        <AdminContext.Provider value={value}>
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
