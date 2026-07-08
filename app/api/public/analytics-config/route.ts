import { NextResponse } from 'next/server';
import { resolveUmamiScriptConfig } from '@/utils/umamiScriptConfig';

export const dynamic = 'force-dynamic';

export function GET() {
  const config = resolveUmamiScriptConfig();

  if (!config) {
    return NextResponse.json(
      { configured: false },
      {
        headers: {
          'Cache-Control': 'no-store',
        },
      },
    );
  }

  return NextResponse.json(
    {
      configured: true,
      websiteId: config.websiteId,
      src: config.src,
    },
    {
      headers: {
        'Cache-Control': 'public, max-age=300, stale-while-revalidate=300',
      },
    },
  );
}
