import React from 'react';
import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { blogPosts, type BlogPostKey } from '../data';
import SaasNav from '@/components/saas/SaasNav';
import BlogArticleContent from './BlogArticleContent';

/* ── Server-side article fetcher ── */

interface APIArticle {
  title: string;
  content: string;
  excerpt: string;
  category: string;
  date?: string;
  created_at?: string;
  published_at?: string;
  estimated_read_minutes?: number;
  readTime?: number;
  og_image?: string;
  card_image?: string;
  author_name?: string;
  meta_title?: string;
  meta_description?: string;
  ogDescription?: string;
}

async function fetchArticleFromAPI(slug: string): Promise<APIArticle | null> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!baseUrl) return null;

    const res = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${slug}`, {
      next: { revalidate: 60 }, // Cache for 60 seconds
    });

    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function getArticleData(apiArticle: APIArticle | null, slug: string) {
  const fallback = blogPosts[slug as BlogPostKey];

  if (apiArticle) {
    return {
      title: apiArticle.title,
      content: apiArticle.content,
      excerpt: apiArticle.excerpt,
      category: apiArticle.category,
      date: apiArticle.created_at || apiArticle.published_at || apiArticle.date || '',
      readTime: apiArticle.estimated_read_minutes || apiArticle.readTime || 5,
      ogDescription: apiArticle.meta_description || apiArticle.ogDescription || apiArticle.excerpt,
      ogImage: apiArticle.og_image || apiArticle.card_image || null,
      authorName: apiArticle.author_name || 'The Special Wedding',
      isMarkdown: true,
      fallbackContent: null,
    };
  }

  if (fallback) {
    return {
      title: fallback.title,
      content: '',
      excerpt: fallback.excerpt,
      category: fallback.category,
      date: fallback.date,
      readTime: fallback.readTime,
      ogDescription: fallback.ogDescription,
      ogImage: null,
      authorName: 'The Special Wedding',
      isMarkdown: false,
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

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />

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
        <div className="prose prose-invert max-w-none">
          {article.isMarkdown ? (
            <BlogArticleContent content={article.content} />
          ) : (
            article.fallbackContent
          )}
        </div>
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

  const ogImages = article.ogImage
    ? [{ url: article.ogImage, width: 1200, height: 630, alt: article.title }]
    : undefined;

  return {
    title: `${article.title} | The Special Wedding Blog`,
    description: article.ogDescription,
    openGraph: {
      title: article.title,
      description: article.ogDescription,
      type: 'article',
      publishedTime: article.date,
      images: ogImages,
    },
    twitter: {
      card: article.ogImage ? 'summary_large_image' : 'summary',
      title: article.title,
      description: article.ogDescription,
      images: article.ogImage ? [article.ogImage] : undefined,
    },
  };
}
