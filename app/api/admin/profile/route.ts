import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET(_request: NextRequest) { // underscore request (not needed; using cookies API)
    try {
        // Get the token from cookies using Next.js cookies()
        const cookieStore = await cookies();
        const token = cookieStore.get('admin_token')?.value;

        if (!token) {
            return NextResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }

        // Forward the request to the backend - using .env as source of truth
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!backendUrl) {
            throw new Error('NEXT_PUBLIC_API_BASE_URL not configured in .env');
        }
        const response = await fetch(`${backendUrl}/admin/profile`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        });

        // Get the response data
        const data = await response.json();

        if (!response.ok) {
            return NextResponse.json(data, { status: response.status });
        }

        // Return the profile data
        return NextResponse.json(data);
    } catch (error) {
        console.error('Profile proxy error:', error);
        return NextResponse.json(
            { detail: 'Failed to fetch profile' },
            { status: 500 }
        );
    }
}