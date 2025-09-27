import { NextRequest, NextResponse } from 'next/server';

// Ensure this route is always dynamic (no caching) and runs on Node.js runtime
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
    let timeout: ReturnType<typeof setTimeout> | null = null;
    try {
        // Get the request body
        const body = await request.json();

        // Resolve backend base URL from server-only env first, then public as fallback
        const backendUrl = process.env.API_BASE_URL || process.env.BACKEND_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
        if (!backendUrl) {
            throw new Error('NEXT_PUBLIC_API_BASE_URL not configured in .env');
        }
        // Add a timeout to avoid hanging requests that could block UI flow
        const controller = new AbortController();
        timeout = setTimeout(() => controller.abort(), 15000);
        const response = await fetch(`${backendUrl}/admin/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
            cache: 'no-store',
            credentials: 'omit',
            signal: controller.signal,
        });
        if (timeout) {
            clearTimeout(timeout);
        }

        // Check content type before parsing to handle HTML error pages gracefully
        const contentType = response.headers.get('content-type');
        let data;

        if (contentType?.includes('application/json')) {
            data = await response.json();
        } else {
            // Backend returned HTML error page (like "Internal Server Error")
            const text = await response.text();
            data = {
                detail: `Backend returned non-JSON response: ${response.status}`,
                error: text.slice(0, 200) // First 200 chars for debugging
            };
        }

        if (!response.ok) {
            return NextResponse.json(data, { status: response.status });
        }

        // Extract the token from the response
        const token: string | undefined = data?.access_token;
        if (!token) {
            return NextResponse.json({ detail: 'Invalid auth response: missing access_token' }, { status: 502 });
        }

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

        return res;
    } catch (err: unknown) {
        if (timeout) {
            clearTimeout(timeout); // Ensure timeout is always cleared
        }

        if ((err as any)?.name === 'AbortError') {
            return NextResponse.json(
                { detail: 'Authentication service timeout' },
                { status: 504 }
            );
        }

        if (err instanceof SyntaxError) {
            console.error('JSON parsing error:', err);
            return NextResponse.json(
                { detail: 'Invalid JSON response from authentication service' },
                { status: 502 }
            );
        }

        type Errno = Error & { code?: string };
        const e = err as Errno;

        if (e.code === 'ECONNREFUSED' || e.code === 'ENOTFOUND') {
            console.error('Connection error:', err);
            return NextResponse.json(
                { detail: 'Authentication service unavailable' },
                { status: 503 }
            );
        }

        if (e.code === 'ETIMEDOUT' || e.code === 'ECONNRESET') {
            console.error('Network timeout error:', err);
            return NextResponse.json(
                { detail: 'Authentication service timeout' },
                { status: 504 }
            );
        }

        console.error('Unexpected login proxy error:', err);
        return NextResponse.json(
            { detail: 'Failed to connect to authentication service' },
            { status: 502 }
        );
    }
}

export async function OPTIONS(_request: NextRequest) { // CORS preflight placeholder - request unused
    return new NextResponse(null, { status: 200 });
}