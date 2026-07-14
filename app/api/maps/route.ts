import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const location = searchParams.get('location');

    if (!location) {
      return NextResponse.json({ error: 'Location is required' }, { status: 400 });
    }

    // Validate location length to prevent abuse
    if (location.length > 500) {
      return NextResponse.json({ error: 'Location too long' }, { status: 400 });
    }

    const apiKey = process.env.GOOGLE_MAPS_API_KEY;

    if (!apiKey) {
      const response = NextResponse.json({ embedUrl: null, mapAvailable: false });
      response.headers.set('Cache-Control', 'no-store');
      return response;
    }

    // Return the embed URL with the server-side API key
    const embedUrl = `https://www.google.com/maps/embed/v1/place?key=${apiKey}&q=${encodeURIComponent(location)}`;

    // Add security headers
    const response = NextResponse.json({ embedUrl, mapAvailable: true });
    response.headers.set('Cache-Control', 'public, max-age=3600'); // Cache for 1 hour

    return response;
  } catch (error) {
    console.error('Maps API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
