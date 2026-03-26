'use client';

import React, { createContext, useContext } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAuth } from './AuthContext';

type APIContextType = {
    apiRequest: <T = any>(path: string, method?: string, body?: unknown) => Promise<T | undefined>;
};

const APIContext = createContext<APIContextType | null>(null);

export const APIProvider = ({ children }: { children: React.ReactNode }) => {
    const { token } = useAuth();

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
        <APIContext.Provider value={{ apiRequest }}>
            {children}
        </APIContext.Provider>
    );
};

export const useAPI = () => {
    const context = useContext(APIContext);
    if (!context) {
        throw new Error('useAPI must be used within APIProvider');
    }
    return context;
};
