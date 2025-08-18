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

    const fetchUserProfile = async () => {
        if (!token) return;
        
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/admin/profile`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const profile = await response.json();
                setUserProfile(profile);
            }
        } catch (error) {
            console.error('Failed to fetch user profile:', error);
        }
    };

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
            const loginUrl = `${baseUrl}/admin/token`;
            console.log('Login URL:', loginUrl); // Debug log
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
            
            // Also set cookie for middleware to check
            document.cookie = `admin_token=${access_token}; path=/; ${rememberMe ? 'max-age=604800' : ''}`;
            
            setToken(access_token);

            toast.success('Login successful');
            router.push('/admin');
        } catch (err: any) {
            toast.error(err.message);
            throw err;
        }
    };


    const logout = () => {
        localStorage.removeItem('admin_token');
        sessionStorage.removeItem('admin_token');
        
        // Remove cookie
        document.cookie = 'admin_token=; path=/; max-age=0';
        
        setToken(null);
        setUserProfile(null);
        toast.success('Logged out');
        router.push('/admin/login');
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

