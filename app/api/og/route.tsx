import { ImageResponse } from 'next/og';
import type { NextRequest } from 'next/server';
import {
  buildBlogCardData,
  buildBlogFallbackCard,
  buildVendorCardData,
  buildVendorFallbackCard,
  fetchBlogArticleForOg,
  fetchVendorForOg,
  type OgCardData,
  type OgTarget,
} from '@/lib/og-utils';

export const runtime = 'edge';
export const dynamic = 'force-dynamic';

const IMAGE_SIZE = { width: 1200, height: 630 };

function resolveTarget(request: NextRequest): OgTarget | null {
  const { searchParams } = request.nextUrl;
  const type = searchParams.get('type');

  if (type === 'blog') {
    const slug = searchParams.get('slug')?.trim();
    if (!slug) return null;
    return { type: 'blog', slug };
  }

  if (type === 'vendor') {
    const id = searchParams.get('id')?.trim();
    if (!id) return null;
    return { type: 'vendor', id };
  }

  return null;
}

function resolvePalette(accent: OgCardData['accent']) {
  if (accent === 'gold') {
    return {
      glow: 'rgba(232,196,106,0.35)',
      glowSoft: 'rgba(232,196,106,0.15)',
      border: 'rgba(232,196,106,0.28)',
      badgeBg: 'rgba(232,196,106,0.16)',
      badgeText: '#f6d46f',
    };
  }

  return {
    glow: 'rgba(212,165,165,0.38)',
    glowSoft: 'rgba(212,165,165,0.16)',
    border: 'rgba(212,165,165,0.28)',
    badgeBg: 'rgba(212,165,165,0.16)',
    badgeText: '#f0b7b7',
  };
}

function OgFrame({
  card,
  brandLine,
}: {
  card: OgCardData;
  brandLine: string;
}) {
  const palette = resolvePalette(card.accent);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        position: 'relative',
        overflow: 'hidden',
        background:
          'linear-gradient(135deg, #090f1f 0%, #0b1120 35%, #111827 100%)',
        color: '#f8fafc',
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            `radial-gradient(circle at 18% 16%, ${palette.glow} 0, transparent 32%),` +
            `radial-gradient(circle at 82% 20%, rgba(232,196,106,0.18) 0, transparent 24%),` +
            'radial-gradient(circle at 50% 100%, rgba(255,255,255,0.06) 0, transparent 30%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage:
            'linear-gradient(180deg, rgba(0,0,0,0.9), rgba(0,0,0,0.25))',
          opacity: 0.28,
        }}
      />

      <div
        style={{
          position: 'relative',
          display: 'flex',
          width: '100%',
          height: '100%',
          padding: '56px',
        }}
      >
        <div
          style={{
            display: 'flex',
            flex: 1,
            borderRadius: '36px',
            border: `1px solid ${palette.border}`,
            background:
              'linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03))',
            boxShadow: '0 32px 90px rgba(0,0,0,0.35)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: '34%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '42px',
              background:
                'linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.025))',
              borderRight: `1px solid ${palette.border}`,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '76px',
                  height: '76px',
                  borderRadius: '24px',
                  background:
                    'linear-gradient(135deg, rgba(212,165,165,0.28), rgba(232,196,106,0.22))',
                  border: `1px solid ${palette.border}`,
                  color: '#fff',
                  fontSize: '24px',
                  fontWeight: 800,
                  letterSpacing: '-0.06em',
                }}
              >
                TSW
              </div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  width: 'fit-content',
                  padding: '8px 14px',
                  borderRadius: '999px',
                  background: palette.badgeBg,
                  color: palette.badgeText,
                  border: `1px solid ${palette.border}`,
                  fontSize: '14px',
                  fontWeight: 700,
                  letterSpacing: '0.18em',
                  textTransform: 'uppercase',
                }}
              >
                {card.badge}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div
                  style={{
                    color: 'rgba(226,232,240,0.7)',
                    fontSize: '18px',
                    fontWeight: 600,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  {card.kicker}
                </div>
                <div
                  style={{
                    color: '#f8fafc',
                    fontSize: '22px',
                    lineHeight: 1.3,
                    fontWeight: 700,
                    maxWidth: '320px',
                  }}
                >
                  {brandLine}
                </div>
              </div>
            </div>

            <div
              style={{
                color: 'rgba(226,232,240,0.65)',
                fontSize: '18px',
                lineHeight: 1.5,
                maxWidth: '280px',
              }}
            >
              {card.footer}
            </div>
          </div>

          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '52px 56px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '20px' }}>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  maxWidth: '760px',
                }}
              >
                <div
                  style={{
                    display: 'inline-flex',
                    width: 'fit-content',
                    padding: '8px 14px',
                    borderRadius: '999px',
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    color: 'rgba(248,250,252,0.8)',
                    fontSize: '14px',
                    fontWeight: 700,
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                  }}
                >
                  {card.kicker}
                </div>
                <div
                  style={{
                    fontSize: '72px',
                    lineHeight: 1.02,
                    letterSpacing: '-0.05em',
                    fontWeight: 800,
                    maxWidth: '760px',
                    display: '-webkit-box',
                    WebkitLineClamp: 4,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {card.title}
                </div>
                <div
                  style={{
                    color: 'rgba(226,232,240,0.82)',
                    fontSize: '26px',
                    lineHeight: 1.4,
                    maxWidth: '680px',
                  }}
                >
                  {card.subtitle}
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  minWidth: '92px',
                }}
              >
                <div
                  style={{
                    width: '92px',
                    height: '92px',
                    borderRadius: '28px',
                    background:
                      'linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04))',
                    border: `1px solid ${palette.border}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    fontSize: '36px',
                    fontWeight: 800,
                  }}
                >
                  {card.badge.slice(0, 1)}
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '16px',
              }}
            >
              <div
                style={{
                  color: 'rgba(226,232,240,0.68)',
                  fontSize: '18px',
                  letterSpacing: '0.16em',
                  textTransform: 'uppercase',
                }}
              >
                {brandLine}
              </div>
              <div
                style={{
                  width: '190px',
                  height: '1px',
                  background:
                    'linear-gradient(90deg, rgba(255,255,255,0.12), rgba(255,255,255,0.5))',
                }}
              />
              <div
                style={{
                  color: 'rgba(226,232,240,0.72)',
                  fontSize: '18px',
                }}
              >
                {card.footer}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildResponse(card: OgCardData, brandLine: string) {
  return new ImageResponse(<OgFrame card={card} brandLine={brandLine} />, {
    ...IMAGE_SIZE,
    headers: {
      'Cache-Control': 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800',
    },
  });
}

export async function GET(request: NextRequest) {
  const target = resolveTarget(request);

  if (!target) {
    return buildResponse(buildBlogFallbackCard(), 'The Special Wedding');
  }

  try {
    if (target.type === 'blog') {
      const article = await fetchBlogArticleForOg(target.slug);
      const card = article ? buildBlogCardData(article) : buildBlogFallbackCard();
      const brandLine = 'The Special Wedding Blog';
      return buildResponse(card, brandLine);
    }

    const vendor = await fetchVendorForOg(target.id);
    const card = vendor ? buildVendorCardData(vendor) : buildVendorFallbackCard();
    const brandLine = 'Public Vendor Profile';
    return buildResponse(card, brandLine);
  } catch {
    if (target?.type === 'vendor') {
      return buildResponse(buildVendorFallbackCard(), 'Public Vendor Profile');
    }

    return buildResponse(buildBlogFallbackCard(), 'The Special Wedding Blog');
  }
}
