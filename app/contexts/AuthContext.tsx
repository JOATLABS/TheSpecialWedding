'use client';

import React from 'react';
import {
    AdminProvider,
    type UserProfile,
    useAdmin,
    useOptionalAdmin,
} from './AdminContext';

export type { UserProfile } from './AdminContext';

type AuthContextType = {
    isAuthenticated: boolean;
    isLoading: boolean;
    token: string | null;
    userProfile: UserProfile | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
    logout: () => void;
    fetchUserProfile: () => Promise<void>;
};

/**
 * Deprecated compatibility provider.
 *
 * New admin code should use AdminProvider/useAdmin directly. This shim keeps
 * the legacy import path working without reintroducing a second auth store.
 */
export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const admin = useOptionalAdmin();

    if (admin) {
        return <>{children}</>;
    }

    return <AdminProvider>{children}</AdminProvider>;
};

export const useAuth = (): AuthContextType => {
    const {
        isAuthenticated,
        isLoading,
        token,
        userProfile,
        login,
        logout,
        fetchUserProfile,
    } = useAdmin();

    return {
        isAuthenticated,
        isLoading,
        token,
        userProfile,
        login,
        logout: () => logout(),
        fetchUserProfile,
    };
};
