import React from 'react';
import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { blogPosts, relatedPosts, type BlogPostKey } from '../data';

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = blogPosts[slug as BlogPostKey];

  if (!post) {
    notFound();
  }

  const related = relatedPosts[slug as BlogPostKey];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header with back link */}
      <div className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="max-w-3xl mx-auto px-6 py-6">
          <Link
            href="/resources"
            className="text-rose-400 hover:text-rose-300 transition-colors text-sm font-medium"
          >
            ← Back to Resources
          </Link>
        </div>
      </div>

      {/* Article content */}
      <article className="max-w-3xl mx-auto px-6 py-12">
        {/* Category and metadata */}
        <div className="mb-8">
          <div className="inline-block">
            <span className="text-xs font-semibold uppercase tracking-wide px-3 py-1 bg-rose-500/20 text-rose-300 rounded-full">
              {post.category}
            </span>
          </div>
          <h1 className="text-4xl font-bold text-white mt-6 mb-4 leading-tight">
            {post.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <time dateTime={post.date}>
              {new Date(post.date).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </time>
            <span>•</span>
            <span>{post.readTime} min read</span>
          </div>
        </div>

        {/* Article body */}
        <div className="prose prose-invert max-w-none mb-12">
          {post.content}
        </div>

        {/* CTA Section */}
        <div className="bg-gradient-to-r from-rose-500/10 to-rose-600/10 border border-rose-500/20 rounded-lg p-8 mb-12">
          <h3 className="text-2xl font-bold text-white mb-3">
            Ready to simplify your workflow?
          </h3>
          <p className="text-slate-300 mb-6">
            The Special Wedding gives wedding planners everything they need in one platform. Guest management, seating orchestration, AI-powered contracts, and more.
          </p>
          <div className="flex gap-4">
            <Link
              href="/admin/login"
              className="inline-block bg-rose-500 hover:bg-rose-600 text-white font-semibold py-3 px-8 rounded-lg transition-colors"
            >
              Start 14-Day Free Trial
            </Link>
            <Link
              href="/resources"
              className="inline-block border border-rose-500 text-rose-300 hover:text-rose-200 font-semibold py-3 px-8 rounded-lg transition-colors"
            >
              Learn More
            </Link>
          </div>
        </div>

        {/* Related posts */}
        <div className="border-t border-slate-800 pt-12">
          <h3 className="text-2xl font-bold text-white mb-8">More from the blog</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {related.slice(0, 2).map((relatedSlug) => {
              const relatedPost = blogPosts[relatedSlug];
              return (
                <Link
                  key={relatedSlug}
                  href={`/resources/blog/${relatedSlug}`}
                  className="group block p-6 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-rose-500/50 transition-colors"
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-rose-400 mb-2">
                    {relatedPost.category}
                  </div>
                  <h4 className="text-lg font-semibold text-white mb-2 group-hover:text-rose-300 transition-colors">
                    {relatedPost.title}
                  </h4>
                  <p className="text-sm text-slate-400 mb-4">
                    {relatedPost.excerpt}
                  </p>
                  <div className="text-xs text-slate-500">
                    {relatedPost.readTime} min read
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </article>
    </main>
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = blogPosts[slug as BlogPostKey];

  if (!post) {
    return {
      title: 'Blog Post Not Found',
      description: 'The blog post you are looking for does not exist.',
    };
  }

  return {
    title: `${post.title} | The Special Wedding Blog`,
    description: post.ogDescription,
    openGraph: {
      title: post.title,
      description: post.ogDescription,
      type: 'article',
      publishedTime: post.date,
    },
  };
}
