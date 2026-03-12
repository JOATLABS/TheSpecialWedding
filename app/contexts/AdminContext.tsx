'use client';

import React, { createContext, useContext } from 'react';
import { AuthProvider, useAuth, type UserProfile } from './AuthContext';
import { APIProvider, useAPI } from './APIContext';

/**
 * AdminContext - Backward compatibility wrapper
 *
 * This context composes the domain-specific contexts:
 * - AuthContext: Authentication state and operations
 * - APIContext: API request functionality
 *
 * New code should use specific hooks (useAuth, useAPI)
 * Existing code can continue using useAdmin() for backward compatibility
 */

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
    return (
        <AuthProvider>
            <APIProvider>
                <AdminProviderContent>{children}</AdminProviderContent>
            </APIProvider>
        </AuthProvider>
    );
};

function AdminProviderContent({ children }: { children: React.ReactNode }) {
    const auth = useAuth();
    const api = useAPI();

    return (
        <AdminContext.Provider
            value={{
                // Auth properties
                isAuthenticated: auth.isAuthenticated,
                isLoading: auth.isLoading,
                token: auth.token,
                userProfile: auth.userProfile,
                // Auth methods
                login: auth.login,
                logout: auth.logout,
                fetchUserProfile: auth.fetchUserProfile,
                // API methods
                apiRequest: api.apiRequest,
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

// Re-export domain-specific hooks for new code
export { useAuth, type UserProfile } from './AuthContext';
export { useAPI } from './APIContext';

