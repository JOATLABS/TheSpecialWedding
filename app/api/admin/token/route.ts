import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
    try {
        // Get the request body
        const body = await request.json();

        // Forward the request to the backend - using .env as source of truth
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!backendUrl) {
            throw new Error('NEXT_PUBLIC_API_BASE_URL not configured in .env');
        }
        const response = await fetch(`${backendUrl}/admin/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        // Get the response data
        const data = await response.json();

        if (!response.ok) {
            return NextResponse.json(data, { status: response.status });
        }

        // Extract the token from the response
        const token = data.access_token;

        // Create the response with the token data
        const res = NextResponse.json(data);

        // Set cookies on the response - this is the correct Next.js pattern
        // 1. Set the httpOnly token cookie for security
        res.cookies.set('admin_token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 604800 // 7 days
        });

        // 2. Set the client-readable auth state cookie
        res.cookies.set('admin_authenticated', 'true', {
            httpOnly: false,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 604800 // 7 days
        });

        // Return the response with cookies properly set
        return res;
    } catch (error) {
        console.error('Login proxy error:', error);
        return NextResponse.json(
            { detail: 'Failed to connect to authentication service' },
            { status: 500 }
        );
    }
}

export async function OPTIONS(request: NextRequest) {
    return new NextResponse(null, { status: 200 });
}