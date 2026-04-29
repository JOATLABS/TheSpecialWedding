import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';
import { blogPosts, type BlogPostKey } from '../data';
import SaasNav from '@/components/saas/SaasNav';
import BreadcrumbSchema from '@/components/seo/BreadcrumbSchema';
import { getMarketingBlogCategory } from '@/data/blogCategories';
import BlogArticleContent from './BlogArticleContent';
import { fetchArticleFromAPI } from '../serverApi';
import {
  allowStaticFallback,
  type PublicBlogApiArticle,
} from '../../resourcesShared';

function getArticleData(apiArticle: PublicBlogApiArticle | null, slug: string) {
  const fallback = allowStaticFallback ? blogPosts[slug as BlogPostKey] : undefined;

  if (apiArticle) {
    return {
      title: apiArticle.title,
      metaTitle: apiArticle.meta_title || null,
      content: apiArticle.content || '',
      excerpt: apiArticle.excerpt,
      category: getMarketingBlogCategory(apiArticle.category),
      date: apiArticle.created_at || apiArticle.published_at || apiArticle.date || '',
      readTime: apiArticle.estimated_read_minutes || apiArticle.readTime || 5,
      ogDescription: apiArticle.meta_description || apiArticle.ogDescription || apiArticle.excerpt,
      ogImage: apiArticle.og_image || apiArticle.card_image || null,
      authorName: apiArticle.author_name || 'The Special Wedding',
      fallbackContent: null as ReactNode | null,
    };
  }

  if (fallback) {
    return {
      title: fallback.title,
      metaTitle: null,
      content: '',
      excerpt: fallback.excerpt,
      category: fallback.category,
      date: fallback.date,
      readTime: fallback.readTime,
      ogDescription: fallback.ogDescription,
      ogImage: null,
      authorName: 'The Special Wedding',
      fallbackContent: fallback.content,
    };
  }

  return null;
}

/* ── Page Component ── */

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const apiArticle = await fetchArticleFromAPI(slug);
  const article = getArticleData(apiArticle, slug);

  if (!article) {
    notFound();
  }

  const formattedDate = article.date
    ? new Date(article.date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '';

  // Use the article-specific OG image if uploaded, otherwise fall back to the
  // dynamic /api/og route which renders a branded card per slug. Either way,
  // BlogPosting.image must be present for Google rich-result eligibility.
  const articleImage = article.ogImage
    ? article.ogImage
    : `https://thespecialwedding.io/api/og?type=blog&slug=${encodeURIComponent(slug)}`;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: article.title,
    description: article.ogDescription,
    datePublished: article.date || undefined,
    // Until we surface an explicit updated_at, mirror datePublished so the
    // schema is complete. When the API returns updated_at, swap it in here.
    dateModified: article.date || undefined,
    image: articleImage,
    author: {
      '@type': article.authorName === 'The Special Wedding' ? 'Organization' : 'Person',
      name: article.authorName,
    },
    publisher: {
      '@type': 'Organization',
      name: 'The Special Wedding',
      url: 'https://thespecialwedding.io',
      logo: {
        '@type': 'ImageObject',
        url: 'https://thespecialwedding.io/logo.svg',
      },
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': `https://thespecialwedding.io/resources/blog/${slug}`,
    },
  };

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      <BreadcrumbSchema
        items={[
          { name: 'Home', href: '/' },
          { name: 'Resources', href: '/resources' },
          { name: article.title, href: `/resources/blog/${slug}` },
        ]}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Article content */}
      <article className="max-w-3xl mx-auto px-6 pt-24 pb-16">
        {/* Back link */}
        <Link
          href="/resources"
          className="text-wedding-rose hover:text-wedding-blush transition-colors text-sm font-medium"
        >
          ← Back to Resources
        </Link>

        {/* Category and metadata */}
        <div className="mt-8 mb-8">
          <div className="inline-block">
            <span className="text-xs font-semibold uppercase tracking-wide px-3 py-1 bg-wedding-rose/20 text-wedding-rose rounded-full">
              {article.category}
            </span>
          </div>
          <h1 className="text-4xl font-bold text-white mt-6 mb-4 leading-tight">
            {article.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            {formattedDate && <time dateTime={article.date}>{formattedDate}</time>}
            {formattedDate && <span>•</span>}
            <span>{article.readTime} min read</span>
            {article.authorName && article.authorName !== 'The Special Wedding' && (
              <>
                <span>•</span>
                <span>{article.authorName}</span>
              </>
            )}
          </div>
        </div>

        {/* Article body */}
        {article.content ? (
          <BlogArticleContent content={article.content} />
        ) : article.fallbackContent ? (
          article.fallbackContent
        ) : (
          <p className="italic text-slate-500">Article content is not available.</p>
        )}
      </article>

      {/* Footer */}
      <footer className="bg-slate-950 border-t border-white/5">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <a href="mailto:hello@thespecialwedding.io" className="text-xs text-slate-500 transition hover:text-slate-300">Contact</a>
              <p className="text-xs text-slate-500">
                Built by{' '}
                <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                  JOATLABS LLC
                </a>
              </p>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}

/* ── Metadata (OG tags) ── */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;

  const apiArticle = await fetchArticleFromAPI(slug);
  const article = getArticleData(apiArticle, slug);

  if (!article) {
    return {
      title: 'Blog Post Not Found',
      description: 'The blog post you are looking for does not exist.',
    };
  }

  const canonicalUrl = `https://thespecialwedding.io/resources/blog/${slug}`;
  const metadataTitle = article.metaTitle || article.title;
  const dynamicOgImage = `/api/og?type=blog&slug=${encodeURIComponent(slug)}`;

  return {
    title: `${metadataTitle} | The Special Wedding Blog`,
    description: article.ogDescription,
    alternates: {
      canonical: canonicalUrl,
    },
    openGraph: {
      title: metadataTitle,
      description: article.ogDescription,
      url: canonicalUrl,
      type: 'article',
      publishedTime: article.date,
      images: [
        {
          url: dynamicOgImage,
          width: 1200,
          height: 630,
          alt: article.title,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      site: '@thespecialwedding',
      title: metadataTitle,
      description: article.ogDescription,
      images: [dynamicOgImage],
    },
  };
}
