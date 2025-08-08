import { NextResponse } from 'next/server';

export async function GET(
  request: Request,
  context: { params: Promise<{ slug: string; token: string }> }
) {
  const params = await context.params;
  
  return NextResponse.json({
    message: 'Route is working',
    slug: params.slug,
    token: params.token,
    timestamp: new Date().toISOString()
  });
}