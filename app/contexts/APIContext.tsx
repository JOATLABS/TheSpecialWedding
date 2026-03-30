'use client';

import React from 'react';
import { AdminProvider, useAdmin, useOptionalAdmin } from './AdminContext';

type APIContextType = {
    apiRequest: <T = any>(path: string, method?: string, body?: unknown) => Promise<T | undefined>;
};

/**
 * Deprecated compatibility provider.
 *
 * New admin code should use AdminProvider/useAdmin directly. This shim keeps
 * the old import path stable without creating another API context layer.
 */
export const APIProvider = ({ children }: { children: React.ReactNode }) => {
    const admin = useOptionalAdmin();

    if (admin) {
        return <>{children}</>;
    }

    return <AdminProvider>{children}</AdminProvider>;
};

export const useAPI = (): APIContextType => {
    const { apiRequest } = useAdmin();

    return { apiRequest };
};
