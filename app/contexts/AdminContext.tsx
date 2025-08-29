'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

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
};

const AdminContext = createContext<AdminContextType | null>(null);

export const AdminProvider = ({ children }: { children: React.ReactNode }) => {
    const router = useRouter();
    const [token, setToken] = useState<string | null>(null);
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);

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
    }, []);

    // Automatically fetch user profile when token is set
    useEffect(() => {
        if (token && !userProfile) {
            fetchUserProfile();
        }
    }, [token, userProfile]);

    const fetchUserProfile = async () => {
        if (!token) return;
        
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
    };

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
            // SECURITY: Clear any existing sessions first to prevent session mixing
            localStorage.removeItem('admin_token');
            sessionStorage.removeItem('admin_token');
            document.cookie = 'admin_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
            
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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

            // Store token in localStorage or sessionStorage
            const storage = rememberMe ? localStorage : sessionStorage;
            storage.setItem('admin_token', access_token);
            
            // Set cookie for middleware to check (with secure attributes)
            const cookieString = `admin_token=${access_token}; path=/; SameSite=Strict; ${rememberMe ? 'max-age=604800;' : 'max-age=3600;'} ${window.location.protocol === 'https:' ? 'Secure;' : ''}`;
            document.cookie = cookieString;
            
            setToken(access_token);

            toast.success('Login successful');
            router.push('/admin');
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    };


    const logout = () => {
        // Clear all possible storage locations
        localStorage.clear(); // Clear ALL localStorage, not just admin_token
        sessionStorage.clear(); // Clear ALL sessionStorage
        
        // Clear ALL cookies, not just admin_token
        document.cookie.split(";").forEach(cookie => {
            const eqPos = cookie.indexOf("=");
            const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
            // Clear for current path and domain
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;`;
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${window.location.hostname}`;
            document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${window.location.hostname}`;
        });
        
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
        <AdminContext.Provider
            value={{
                isAuthenticated: !!token,
                token,
                userProfile,
                login,
                logout,
                fetchUserProfile,
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

