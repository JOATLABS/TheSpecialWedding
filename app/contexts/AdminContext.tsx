'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

type AdminContextType = {
    isAuthenticated: boolean;
    token: string | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
};

const AdminContext = createContext<AdminContextType | null>(null);

export const AdminProvider = ({ children }: { children: React.ReactNode }) => {
    const router = useRouter();
    const [token, setToken] = useState<string | null>(null);

    useEffect(() => {
        const stored = localStorage.getItem('admin_token');
        if (stored) {
            setToken(stored);
        }
    }, []);

    const login = async (email: string, password: string, rememberMe = true) => {
        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
            const res = await fetch(`${baseUrl}/admin/token`, {
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
            router.push('/admin/gallery/upload');
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
        toast.success('Logged out');
        router.push('/admin/login');
    };

    return (
        <AdminContext.Provider
            value={{
                isAuthenticated: !!token,
                token,
                login,
                logout,
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

