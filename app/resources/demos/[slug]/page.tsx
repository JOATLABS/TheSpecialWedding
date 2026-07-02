import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import {
  MARKETING_DEMO_VIDEO_PAGES,
  formatIso8601Duration,
  getMarketingDemoVideoBySlug,
  getMarketingDemoVideoCaptionsUrl,
  getMarketingDemoVideoCanonicalPath,
  getMarketingDemoVideoCanonicalUrl,
  getMarketingDemoVideoContentUrl,
  getMarketingDemoVideoThumbnailUrl,
  isMarketingDemoVideoIndexable,
} from '@/data/marketingDemoVideos';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';
import { serializeJsonLd } from '@/seo/jsonLd';

import SaasNav from '../../../components/saas/SaasNav';

type DemoVideoPageParams = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return MARKETING_DEMO_VIDEO_PAGES.map((video) => ({ slug: video.slug }));
}

export async function generateMetadata({ params }: DemoVideoPageParams): Promise<Metadata> {
  const { slug } = await params;
  const video = getMarketingDemoVideoBySlug(slug);
  if (!video) return {};

  const canonicalPath = getMarketingDemoVideoCanonicalPath(video);
  const canonicalUrl = getMarketingDemoVideoCanonicalUrl(video);
  const thumbnailUrl = getMarketingDemoVideoThumbnailUrl(video);
  const shouldIndex = isMarketingDemoVideoIndexable(video);

  return {
    title: video.seoTitle,
    description: video.description,
    alternates: {
      canonical: canonicalPath,
    },
    openGraph: {
      title: video.title,
      description: video.description,
      url: canonicalUrl,
      siteName: 'The Special Wedding',
      type: 'website',
      images: [
        {
          url: thumbnailUrl,
          width: video.width,
          height: video.height,
          alt: `${video.title} poster`,
        },
      ],
    },
    robots: {
      index: shouldIndex,
      follow: shouldIndex,
    },
  };
}

export default async function MarketingDemoVideoPage({ params }: DemoVideoPageParams) {
  const { slug } = await params;
  const video = getMarketingDemoVideoBySlug(slug);
  if (!video) notFound();

  const canonicalPath = getMarketingDemoVideoCanonicalPath(video);
  const canonicalUrl = getMarketingDemoVideoCanonicalUrl(video);
  const contentUrl = getMarketingDemoVideoContentUrl(video);
  const captionsUrl = getMarketingDemoVideoCaptionsUrl(video);
  const thumbnailUrl = getMarketingDemoVideoThumbnailUrl(video);
  const shouldIndex = isMarketingDemoVideoIndexable(video);

  const videoJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    name: video.title,
    description: video.description,
    thumbnailUrl: [thumbnailUrl],
    uploadDate: video.uploadDate,
    duration: formatIso8601Duration(video.durationSeconds),
    contentUrl,
    embedUrl: canonicalUrl,
    publisher: {
      '@type': 'Organization',
      name: 'The Special Wedding',
      url: 'https://thespecialwedding.io',
    },
    potentialAction: {
      '@type': 'WatchAction',
      target: canonicalUrl,
    },
  };

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources/blog' },
          { name: 'Product Demos', href: '/resources/demos' },
          { name: video.title, href: canonicalPath },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(videoJsonLd) }}
      />

      <section className="border-b border-white/10 px-6 pb-12 pt-32 sm:px-10">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1fr_0.42fr] lg:items-end">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-wedding-rose">
              Product demo video
            </p>
            <h1 className="mt-4 max-w-3xl text-3xl font-semibold leading-tight sm:text-5xl">
              {video.title}
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300">
              {video.description}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 text-sm leading-6 text-slate-300">
            <p className="font-semibold text-white">Audience</p>
            <p className="mt-2">{video.audience}</p>
            <dl className="mt-5 grid grid-cols-2 gap-4 text-xs uppercase tracking-[0.2em] text-slate-500">
              <div>
                <dt>Length</dt>
                <dd className="mt-1 text-sm normal-case tracking-normal text-slate-200">
                  {Math.round(video.durationSeconds)} seconds
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd className="mt-1 text-sm normal-case tracking-normal text-slate-200">
                  {video.publicationStatus === 'published' ? 'Published' : 'Review-ready'}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
        {!shouldIndex && (
          <div className="mb-5 rounded-2xl border border-amber-300/30 bg-amber-300/10 p-4 text-sm leading-6 text-amber-100">
            This page is wired for R2/CDN publishing, but it is excluded from search indexing until the final
            upload, pacing review, and audio direction are approved.
          </div>
        )}
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-black shadow-2xl shadow-black/30">
          <video
            className="h-full w-full bg-black object-contain"
            controls
            playsInline
            preload="metadata"
            poster={thumbnailUrl}
            style={{ aspectRatio: `${video.width} / ${video.height}` }}
          >
            <source src={contentUrl} type="video/mp4" />
            {captionsUrl && (
              <track
                kind="captions"
                src={captionsUrl}
                srcLang="en"
                label="English"
                default
              />
            )}
          </video>
        </div>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Link
            href={PUBLIC_LOGIN_PATH}
            className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
          >
            Start with one wedding free
          </Link>
          <Link
            href="/resources/demos"
            className="inline-flex items-center justify-center rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-white transition hover:border-wedding-rose/50 hover:text-wedding-rose"
          >
            Browse all product demos
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-16 sm:px-10 lg:grid-cols-[0.62fr_0.38fr]">
        <article className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
          <h2 className="text-2xl font-semibold">What this walkthrough shows</h2>
          <ol className="mt-5 space-y-4">
            {video.chapters.map((chapter) => (
              <li key={`${chapter.startSeconds}-${chapter.title}`} className="border-l border-wedding-rose/40 pl-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-wedding-rose">
                  {Math.floor(chapter.startSeconds / 60)}:{String(chapter.startSeconds % 60).padStart(2, '0')}
                </p>
                <h3 className="mt-1 font-semibold text-white">{chapter.title}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-400">{chapter.description}</p>
              </li>
            ))}
          </ol>
        </article>
        <aside className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
          <h2 className="text-2xl font-semibold">Transcript summary</h2>
          <div className="mt-5 space-y-3 text-sm leading-6 text-slate-300">
            {video.transcriptSummary.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
          <div className="mt-6 rounded-xl border border-white/10 bg-slate-900/80 p-4 text-xs leading-6 text-slate-400">
            Final marketing MP4s should be uploaded to R2 under this page&apos;s stable object keys. This
            route provides the canonical SEO endpoint; the CDN object provides the video bytes.
          </div>
        </aside>
      </section>
    </main>
  );
}
