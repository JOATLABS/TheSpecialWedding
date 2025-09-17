import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function POST(request: NextRequest) {
    try {
        // Get the token from cookies for the backend call
        const cookieStore = await cookies();
        const token = cookieStore.get('admin_token')?.value;

        // Forward the request to the backend - using .env as source of truth
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!backendUrl) {
            throw new Error('NEXT_PUBLIC_API_BASE_URL not configured in .env');
        }
        const response = await fetch(`${backendUrl}/admin/logout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
        });

        // Get the response data
        const data = await response.json();

        // Create response and clear cookies using the correct pattern
        const res = NextResponse.json(data);
        res.cookies.delete('admin_token');
        res.cookies.delete('admin_authenticated');

        return res;
    } catch (error) {
        console.error('Logout proxy error:', error);
        // Even if backend fails, clear the cookies
        const res = NextResponse.json({ message: 'Logged out successfully' });
        res.cookies.delete('admin_token');
        res.cookies.delete('admin_authenticated');
        return res;
    }
}